#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 Setup for the package
"""

from setuptools import setup
setup(
    entry_points={
        'console_scripts': [
            'seminar_screencast=seminar_screencaster:main',
        ],
    },
    name='seminar_screencaster',
    version='1.01',
    packages=['seminar_screencaster'],
    author_email = "stanislav.fomin@gmail.com",

)

