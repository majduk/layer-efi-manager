# Overview

This charm is intended to create software RAID for EFI partition.

# Usage

This charm is a subordinate charm. This means it must be attached to a another application.

```
juju deploy efi-manager
juju juju add-relation efi-manager <yourapp>
```



## Scale out Usage

Scale the application which this charm is subordinate to.

# Configuration

None
