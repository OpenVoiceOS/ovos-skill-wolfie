#!/usr/bin/env python3
from setuptools import setup

# skill_id=package_name:SkillClass
PLUGIN_ENTRY_POINT = 'skill-wolfie.jarbasai=skill_wolfie:WolframAlphaSkill'

setup(
    # this is the package name that goes on pip
    name='skill-wolfie',
    version='0.0.1',
    description='mycroft/ovos wolfram alpha skill plugin',
    url='https://github.com/JarbasSkills/skill-wolfie',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    package_dir={"skill_wolfie": ""},
    package_data={'skill_wolfie': ['locale/*', 'vocab/*', "dialog/*"]},
    packages=['skill_wolfie'],
    include_package_data=True,
    install_requires=["ovos-plugin-manager>=0.0.1a3",
                      "neon-solver-wolfram-alpha-plugin",
                      "neon-solvers"],
    keywords='ovos skill plugin',
    entry_points={'ovos.plugin.skill': PLUGIN_ENTRY_POINT}
)
