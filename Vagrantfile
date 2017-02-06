# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "bento/ubuntu-16.04"
  config.vm.synced_folder "./", "/opt/fingerprint-securedrop/", disabled: false
  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "playbooks/vagrant-playbook.yml"
    # Hack to support CLI options such as `--tags` and `--skip-tags`.
    ansible.raw_arguments = Shellwords.shellsplit(ENV['ANSIBLE_ARGS']) if ENV['ANSIBLE_ARGS']
    ansible.verbose = "vv"
  end
  config.vm.provider "virtualbox" do |vb|
    # Additional RAM since we're compiling tor source.
    vb.memory = 1024
    vb.customize ["modifyvm", :id, "--cpus", available_vcpus]
  end
  config.vm.provider "libvirt" do |lv|
    lv.memory = 1024
    lv.cpus = available_vcpus
    config.vm.synced_folder './', '/vagrant', type: 'nfs', disabled: false
  end
end

def available_vcpus
  # Increase number of virtual CPUs in guest VM.
  # Rather than blindly set it to "2" or similar,
  # inspect the number of VCPUs on the host and use that,
  # to minimize compile time.
  available_vcpus = case RUBY_PLATFORM
    when /linux/
      `nproc`.to_i
    when /darwin/
      `sysctl -n hw.ncpu`.to_i
    else
      1
    end
  # If you want to restrict the resources available to the guest VM,
  # uncomment the return line below, and Vagrant will use half the
  # number available on the host, rounded down.
  # (Ruby will correctly return the quotient as an integer.)
  # return available_vcpus / 2
  return available_vcpus
end
