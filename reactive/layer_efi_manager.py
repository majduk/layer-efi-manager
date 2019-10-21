from charms.reactive import when, when_not, set_flag
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


def clone_data(source, dest):
    subprocess.call(['dd', 'if={}'.format(source), 'of={}'.format(dest)])


def add_efi_entry(part):
    subprocess.call(['efibootmgr', '-c', '-g', '-d',
                     '/dev/{}'.format(part['name']),
                     '-p', '1', '-L', 'ubuntu#2',
                     '-l', '\\EFI\\ubuntu\\shimx64.efi'])


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
    mount('/dev/md100', master_partition['mountpoint'])
    grow_raid('/dev/md100', master_partition)
    add_efi_entry(slave_partition)
    set_flag('layer-efi-manager.installed')
