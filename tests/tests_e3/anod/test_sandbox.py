from __future__ import absolute_import, division, print_function

import os
from shutil import copyfile

import e3.anod.sandbox
import e3.env
import e3.fs
import e3.os.process
import e3.platform
from e3.vcs.git import GitRepository

import pytest


def test_deploy_sandbox():
    sandbox_dir = os.getcwd()
    e3.os.process.Run(
        ['e3-sandbox', '-v', '-v', 'create', sandbox_dir], output=None)
    assert os.path.isdir('log')

    assert 'sandbox = %s' % sandbox_dir in e3.os.process.Run(
        ['e3-sandbox', 'show-config', sandbox_dir]).out

    e3.fs.mkdir('specs')

    with open(os.path.join('specs', 'a.anod'), 'w') as fd:
        fd.write('from e3.anod.spec import Anod\n')
        fd.write('class A(Anod):\n')
        fd.write('    pass\n')

    assert 'no primitive download' in e3.os.process.Run(
        [os.path.join('bin', 'anod'),
         'download', 'a']).out

    with open(os.path.join('specs', 'b.anod'), 'w') as fd:
        fd.write('from e3.anod.spec import Anod\n')
        fd.write('class B(Anod):\n\n')
        fd.write('    @Anod.primitive()\n')
        fd.write('    def download(self):\n')
        fd.write('        pass\n')

    assert 'cannot get resource metadata from store' in e3.os.process.Run(
        [os.path.join('bin', 'anod'),
         'download', 'b']).out


def test_sandbox_env():
    os.environ['GPR_PROJECT_PATH'] = '/foo'
    sandbox = e3.anod.sandbox.SandBox()
    sandbox.set_default_env()
    assert os.environ['GPR_PROJECT_PATH'] == ''


@pytest.mark.git
def test_SandBoxCreate_git():
    """Check if sandbox create can load the specs from a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')
    specs_dir = os.path.join(root_dir, 'e3-specs')
    # prepare git repo
    prepare_git(specs_dir)
    with_git = e3.os.process.Run(
        ['e3-sandbox', '-v',
         'create',
         '--spec-git-url', specs_dir,
         sandbox_dir], output=None)
    assert with_git.status == 0
    # Test structure
    for test_dir in ['bin', 'log', 'meta', 'patch',
                     'specs', 'src', 'tmp', 'vcs']:
                    assert os.path.isdir(os.path.join(sandbox_dir, test_dir))
    # Test specs files if created
    specs_files = ['anod.anod', 'e3.anod', 'python-virtualenv.anod',
                   'conf.yaml', 'prolog.py']
    for filename in specs_files:
        assert os.path.isfile(os.path.join(sandbox_dir, 'specs', filename))


@pytest.mark.git
def test_sandbox_exec_missing():
    """Test sandbox exec exception.

    - Check if sandbox exec raises exception if spec-dir is missing
    - Check if sandbox exec raises exception if plan file is missing
    """
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')
    specs_dir = os.path.join(root_dir, 'e3-specs')
    prepare_git(specs_dir)

    e3.os.process.Run(['e3-sandbox', 'create', sandbox_dir], output=None)

    # Specs dir is missing
    no_specs = e3.os.process.Run(['e3-sandbox', 'exec',
                                  '--spec-dir', 'nospecs',
                                  '--plan',
                                  'noplan', sandbox_dir])
    assert no_specs.status != 0
    assert 'spec directory nospecs does not exist' in no_specs.out

    # Plan file is missing
    no_plan = e3.os.process.Run(['e3-sandbox', 'exec',
                                 '--spec-git-url', specs_dir,
                                 '--plan', 'noplan',
                                 '--create-sandbox',
                                 sandbox_dir])
    assert no_plan.status != 0
    assert 'SandBoxExec.run: plan file noplan does not exist' in no_plan.out


@pytest.mark.git
def test_sandbox_exec_success():
    """Test if sandbox exec works with local specs and a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')
    specs_dir = os.path.join(root_dir, 'e3-specs')

    # Prepare a git repo
    prepare_git(specs_dir)
    platform = e3.platform.Platform.get().platform

    e3.os.process.Run(['e3-sandbox', 'create', sandbox_dir], output=None)
    with open(os.path.join(sandbox_dir, 'test.plan'), 'w') as fd:
        fd.write("anod_build('e3')\n")

    # Test with local specs
    p = e3.os.process.Run(['e3-sandbox', 'exec',
                           '--spec-dir', specs_dir,
                           '--plan',
                           os.path.join(sandbox_dir, 'test.plan'),
                           sandbox_dir])
    assert 'build e3 for %s' % platform in p.out

    # Test with git module
    p = e3.os.process.Run(['e3-sandbox', 'exec',
                           '--spec-git-url', specs_dir,
                           '--plan',
                           os.path.join(sandbox_dir, 'test.plan'),
                           '--create-sandbox', sandbox_dir])
    assert 'build e3 for %s' % platform in p.out


@pytest.mark.git
def test_anod_plan():
    """Test if sandbox exec works with local specs and a git repo."""
    root_dir = os.getcwd()
    sandbox_dir = os.path.join(root_dir, 'sbx')
    specs_dir = os.path.join(root_dir, 'e3-specs')

    # Prepare a git repo
    prepare_git(specs_dir)

    # create sandbox
    with_git = e3.os.process.Run(['e3-sandbox', '-v',
                                  'create',
                                  '--spec-git-url', specs_dir,
                                  sandbox_dir], output=None)
    assert with_git.status == 0

    # Test anod build
    platform = e3.platform.Platform.get().platform

    # Build action
    with open(os.path.join(root_dir, 'e3_build.plan'), 'w') as fd:
        fd.write("anod_build('e3')")
    command = ['e3-sandbox', '-v', 'exec',
               '--plan', os.path.join(root_dir, 'e3_build.plan'),
               sandbox_dir]
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['build e3 for %s' % platform, ]
    for action in actions:
        assert action in p.out

    # Install action
    with open(os.path.join(root_dir, 'e3_build.plan'), 'w') as fd:
        fd.write("anod_install('e3')")
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['download binary of %s.e3' % platform,
               'install e3 for %s' % platform]
    for action in actions:
        assert action in p.out

    # Test action
    with open(os.path.join(root_dir, 'e3_build.plan'), 'w') as fd:
        fd.write("anod_test('e3')")
    p = e3.os.process.Run(command)
    assert p.status == 0
    actions = ['download source e3-core-src',
               'build python-virtualenv for %s' % platform,
               'get source e3-core-src',
               'install source e3-core-src',
               'test e3 for %s' % platform]
    for action in actions:
        assert action in p.out


def prepare_git(specs_dir):
    """Create a git repo to check out specs from it.

    :param spec_dir: directory to create the git repo in it
    :type spec_dir: str
    """
    # Create the git repo if it doesnt exist
    if not os.path.isdir(specs_dir):
        os.mkdir(specs_dir)
    specs_source_dir = os.path.join(os.path.dirname(__file__), 'specs')
    for spec_file in os.listdir(specs_source_dir):
        if os.path.isfile(os.path.join(specs_source_dir, spec_file)):
            copyfile(os.path.join(specs_source_dir, spec_file),
                     os.path.join(specs_dir, spec_file))
    # Put prolog file
    create_prolog(specs_dir)
    if os.path.isdir(os.path.join(specs_dir, '.git')):
        return
    # As prolog.py has been created on the fly we will commit all files here
    g = GitRepository(specs_dir)
    g.init()
    g.git_cmd(['config', 'user.email', '"test@example.com"'])
    g.git_cmd(['config', 'user.name', '"test"'])
    g.git_cmd(['add', '-A'])
    g.git_cmd(['commit', '-m', "'add all'"])


def create_prolog(prolog_dir):
    """Create prolog.py file on the fly to prevent checkstyle error."""
    if os.path.isfile(os.path.join(prolog_dir, 'prolog.py')):
        return
    prolog_content = """# prolog file loaded before all specs


def main():
    import yaml
    import os

    with open(os.path.join(
            __spec_repository.spec_dir, 'conf.yaml')) as f:
        conf = yaml.load(f)
        __spec_repository.api_version = conf['api_version']


main()
del main
"""
    with open(os.path.join(prolog_dir, 'prolog.py'), 'w') as fd_prolog:
        fd_prolog.write(prolog_content)
