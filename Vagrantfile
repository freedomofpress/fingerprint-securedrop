# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "bento/ubuntu-16.04"
  config.vm.synced_folder "./", "/opt/FingerprintSecureDrop/", disabled: false
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook.yml"
    # Hack to support CLI options such as `--tags` and `--skip-tags`.
    ansible.raw_arguments = Shellwords.shellsplit(ENV['ANSIBLE_ARGS']) if ENV['ANSIBLE_ARGS']
    ansible.verbose = "vv"
  end
  config.vm.provider "virtualbox" do |vb|
    # Additional RAM since we're compiling tor source.
    vb.memory = 1024
  end
end
