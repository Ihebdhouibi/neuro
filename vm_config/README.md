# Windows 10 Test VM (VirtualBox)

## Configuration
- **RAM**: 8192 MB
- **CPUs**: 2
- **Disk**: 80.68 GB
- **OS**: Windows 10 (64-bit)
- **EFI**: disabled

## How to use
1. Install VirtualBox.
2. Import `Test.vbox` (File → Add Machine).
3. Attach a Windows 10 ISO (evaluation or licensed) to the optical drive.
4. Start the VM and install Windows.
5. After installation, install Guest Additions for better integration.

## Notes
- The `.vdi` disk file is **not** included in Git (large binary). It is located at `C:\Users\hp\VirtualBox VMs\Test\Test.vdi` on the original host.
- To recreate the disk, create a new VM with the same settings or use `VBoxManage` commands.
