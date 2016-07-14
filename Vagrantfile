# -*- mode: ruby -*-
# vi: set ft=ruby :


$success_message = <<MESSAGE
You must manually enable the shared folder in the Vagrantfile.
Edit the 'config.vm.synced_folder' line and set 'disabled' to 'false',
then run 'vagrant reload --provision' to reboot and mount the shared folder.
We do apologize for the inconvenience. Upstream changes are pending
to avoid this manual bootstrapping process in the future.
MESSAGE

$script = <<SCRIPT
echo "Configuring shared folder under Ubuntu 16.04..."
sudo apt-get --no-install-recommends install -y virtualbox-guest-utils
sudo apt-get install -y python # necessary for Ansible support

if [[ ! -d /home/ubuntu/FingerprintSecureDrop ]]; then
echo "#{$success_message}" 1>&2 &&
exit 1
fi
SCRIPT

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/xenial64"
  config.vm.synced_folder "./", "/home/ubuntu/FingerprintSecureDrop/", disabled: true

  # The /vagrant shared folder functionality is broken in Ubuntu 16.04, see:
  # https://bugs.launchpad.net/cloud-images/+bug/1565985
  # So let's handle the automagic ourselves.
  config.vm.provision "shell", inline: $script

  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook.yml"
    # Hack to support CLI options such as `--tags` and `--skip-tags`.
    ansible.raw_arguments = Shellwords.shellsplit(ENV['ANSIBLE_ARGS']) if ENV['ANSIBLE_ARGS']
    ansible.verbose = "v"
  end
end
