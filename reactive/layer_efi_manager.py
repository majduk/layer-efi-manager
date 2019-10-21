from charms.reactive import when, when_not, set_flag
from charmhelpers.core.templating import render
import subprocess
import json


def get_efi_eligible():
    devs_output = subprocess.check_output(['lsblk', '--json', '-f'])
    devs = json.loads(devs_output)
    parts = []
    for dev in devs['blockdevices']:
        for part in dev['children']:
            if part['fstype'] == 'vfat':
                parts.append(part)
    return parts


def is_mounted(part):
    return part['mountpoint'] is not None


def disable_mount(part):
    subprocess.call(['sed', '-i.bak',
                     '/UUID={}/d'.format(part['uuid']), '/etc/fstab'])


def umount(part):
    subprocess.call(['umount', part['mountpoint']])


def mount(part, mountpoint):
    subprocess.call(['mount', part, mountpoint])


def zero_mbr(part):
    subprocess.call(
            ['dd',
             'if=/dev/zero',
             'of=/dev/{}'.format(part['name'], 'bs=512', 'count=1')])


def create_raid(part, raid):
    subprocess.call(['mdadm', '--create', raid,
                     '--force', '--level', '1', '--raid-disks', '1',
                     '--metadata', '1.0', '/dev/{}'.format(part['name'])])


def grow_raid(raid, part):
    subprocess.call(['mdadm', '--grow', raid, '--raid-devices=2',
                     '--add', '/dev/{}'.format(part['name'])])


def get_raid_uuid(raid):
    out = subprocess.check_output(['mdadm', '--detail', raid])
    for line in out.decode().split('\n'):
        if 'UUID' in line:
            return line.split(':', 1)[1].strip()


def clone_data(source, dest):
    subprocess.call(['dd', 'if={}'.format(source), 'of={}'.format(dest)])


def add_efi_entry(part):
    subprocess.call(['efibootmgr', '-c', '-g', '-d',
                     '/dev/{}'.format(part['name']),
                     '-p', '1', '-L', 'ubuntu#2',
                     '-l', '\\EFI\\ubuntu\\shimx64.efi'])


def add_fstab_entry(device):
    with open('/etc/fstab', 'a+') as f:
        line = '{} /boot/efi vfat noauto,defaults 0 0'.format(device)
        f.write(line + '\n')


def add_mdadm_entry(uuid):
    with open('/etc/mdadm/mdadm.conf', 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        line = 'ARRAY <ignore> UUID={}'.format(uuid)
        f.write(line.rstrip('\r\n') + '\n' + content)


@when_not('layer-efi-manager.installed')
def install_layer_efi_manager():
    parts = get_efi_eligible()
    for part in parts:
        if is_mounted(part):
            master_partition = part
        else:
            slave_partition = part
    zero_mbr(slave_partition)
    create_raid(slave_partition, '/dev/md100')
    clone_data('/dev/{}'.format(master_partition['name']), '/dev/md100')
    umount(master_partition)
    grow_raid('/dev/md100', master_partition)
    add_efi_entry(slave_partition)

    add_fstab_entry('/dev/md100')
    service = 'efi-resync'
    service_file = '/etc/systemd/system/{}.service'.format(service)
    service_template = 'service.j2'
    context = {
        'uuid': get_raid_uuid('/dev/md100'),
        'device': '/dev/md100',
        'mountpoint': master_partition['mountpoint']
    }
    render(service_template, service_file, context, perms=0o755)
    add_mdadm_entry(get_raid_uuid('/dev/md100'))
    subprocess.check_call(['update-initramfs', '-u'])
    # Enable and start the one-shot service
    cmd = 'systemctl enable {}'.format(service)
    subprocess.check_call(cmd, shell=True)
    cmd = 'systemctl start {}'.format(service)
    subprocess.check_call(cmd, shell=True)
    set_flag('layer-efi-manager.installed')
