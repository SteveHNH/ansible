#!/usr/bin/python

from ansible.module_utils.basic import *


class grubby(object):

    def __init__(self, module, info, args):
        self.info = info
        self.module = module
        self.args = args
        self.kernels = ['DEFAULT', 'ALL']
        self.major_ver = get_distribution_version()

        self.get_kernel_versions()

    def get_kernel_versions(self):
        for k in self.info:
            self.kernels.append(k)

    def get_kernel_args(self):
        kernel_args = []
        kernel = self.args['name']
        # need to behave differently if Default or All is chosen. This changes
        # specific kernel
        if kernel != 'DEFAULT' and kernel != 'ALL':
            kernel_args.append(self.info[kernel].get('args').split())
        else:
        # This will gather args from all kernels
            for k in self.info:
                joined = [self.info[k].get('args').split()]
                for i in joined:
                    kernel_args = kernel_args + i
        return kernel_args

    def kernel_arg_change(self):
        kernel = self.args['name']
        if kernel != 'DEFAULT' and kernel != 'ALL':
            kernel_args = self.get_kernel_args()[0]
        else:
            kernel_args = self.get_kernel_args()
        match = [i for i in self.args['args'].split() if i in kernel_args]
        kernel = self.args['name']
        if self.args['state'] == 'present':
            if match == self.args['args'].split():
                return
            #TODO remove sudo
            command = ['sudo', self.module.get_bin_path('grubby', True), '--update-kernel', kernel, '--args']
            # fix this join thing. Stuff keeps coming out as a list
            command.append(self.args['args'])
        if self.args['state'] == 'absent':
            if match != self.args['args'].split():
                return
            #TODO remove sudo
            command = ['sudo', self.module.get_bin_path('grubby', True), '--update-kernel', kernel, '--remove-args']
            # fix this join thing. Stuff keesp coming out as a list
            command.append(self.args['args'])

        self.args['command'] = command

        if kernel in self.kernels:
            rc, _, err = self.module.run_command(command)
            if rc != 0:
                self.module.exit_json(msg=err, **self.args)
            self.args['changed'] = True
        else:
            self.module.exit_json(changed=False, Failed=True, msg="Specified kernel is not installed: %s" % kernel)

    def set_default_kernel(self):
        kernel = self.args['name']
        if kernel == self.get_default_kernel():
            return
        if kernel == 'ALL':
            self.module.exit_json(changed=False, Failed=True, msg="Must choose one kernel when setting default")
        # TODO  remove sudo
        command = ['sudo', self.module.get_bin_path('grubby', True), '--set-default', kernel]
        if kernel in self.kernels:
            rc, _, err = self.module.run_command(command)
            if rc != 0:
                self.module.exit_json(msg=err, **self.args)
            self.args['changed'] = True
        else:
            self.module.exit_json(changed=False, Failed=True, msg="Specified kernel is not installed: %s" % kernel)

    def get_default_kernel(self):
        command = ['sudo', self.module.get_bin_path('grubby', True), '--info', 'DEFAULT']
        rc, _, err = self.module.run_command(command)
        default_kernel = _.splitlines()[1].split('=')[1]
        return default_kernel

def main():
    module = AnsibleModule(
        argument_spec={
            'name': {'default': 'default'},
            'set_default': {'required': False, type: 'bool'},
            'state': {'default': 'present',
                      'choices': ['absent', 'present'],
                      'required': False},
            'args': {'required': False},
        },
        supports_check_mode=False
    )

    args = {
        'name': module.params['name'],
        'set_default': module.params['set_default'],
        'state': module.params['state'],
        'args': module.params['args'].replace(',', ''),
        'changed': False,
        'failed': False
    }

    if args['name'] == 'default' or args['name'] == 'all':
        args['name'] = args['name'].upper()

    if args['name'] != 'DEFAULT' and args['name'] != 'ALL':
        if not args['name'].startswith('/boot/'):
            args['name'] = '/boot/' + args['name']

    kern_re = re.compile(r'^kernel=(.+$)', re.M)
    command = [module.get_bin_path('grubby', True), '--info=ALL']

    grub_out = module.run_command(command)[1]

    d = dict([(k, {}) for k in kern_re.findall(grub_out)])

    subdict = {}
    kern = None

    # create the dictionary of grubby info
    for line in grub_out.splitlines():
        if kern_re.search(line):
            if kern:
                d[kern] = subdict
            kern = kern_re.search(line).groups()[0]
            subdict = {}
        else:
            if line.startswith('index') or line.startswith('boot'):
                continue
            key, value = line.partition('=')[::2]
            subdict[key] = value.replace('"', '')

    d = dict([(k, v) for k, v in d.items() if d[k] != {}])
    for k in d:
        d[k]['args'] = d[k]['args'].replace('"', '')

    gc = grubby(module, d, args)

    if args['args']:
        gc.kernel_arg_change()

    if args['set_default']:
        gc.set_default_kernel()

    module.exit_json(**args)

if __name__ == '__main__':
    main()
