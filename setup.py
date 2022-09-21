#!/usr/bin/env python3
from setuptools import setup

# skill_id=package_name:SkillClass
PLUGIN_ENTRY_POINT = 'skill-ovos-wolfie.openvoiceos=skill_wolfie:WolframAlphaSkill'

setup(
    # this is the package name that goes on pip
    name='skill-ovos-wolfie',
    version='0.0.1',
    description='mycroft/ovos wolfram alpha skill plugin',
    url='https://github.com/OpenVoiceOS/skill-ovos-wolfie',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    package_dir={"skill_ovos_wolfie": ""},
    package_data={'skill_ovos_wolfie': ['locale/*', 'vocab/*', "dialog/*"]},
    packages=['skill_ovos_wolfie'],
    include_package_data=True,
    install_requires=["ovos-plugin-manager>=0.0.1a3",
                      "neon-solver-wolfram-alpha-plugin",
                      "neon-solvers"],
    keywords='ovos skill plugin',
    entry_points={'ovos.plugin.skill': PLUGIN_ENTRY_POINT}
)
