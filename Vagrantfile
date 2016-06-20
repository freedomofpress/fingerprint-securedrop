# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  config.vm.synced_folder "./", "/home/vagrant/FingerprintSecureDrop/", disabled: false
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbook.yml"
  end
end
