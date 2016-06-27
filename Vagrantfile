# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  # config.vm.box = "debian/contrib-jessie64"
  config.vm.synced_folder "./", "/home/vagrant/FingerprintSecureDrop/", disabled: false
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook.yml"
    # Hack to support CLI options such as `--tags` and `--skip-tags`.
    ansible.raw_arguments = Shellwords.shellsplit(ENV['ANSIBLE_ARGS']) if ENV['ANSIBLE_ARGS']
    ansible.verbose = "v"
  end
end
