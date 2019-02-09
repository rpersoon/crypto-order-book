# Copyright (c) 2017 - 2019 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


from setuptools import setup

setup(
   name='crypto_order_book',
   version='1.0.0',
   description='Cryptocurrency exchange order book',
   author='Ricardo Persoon',
   packages=['crypto_order_book'],
   install_requires=['sortedcontainers', 'websocket-client'],
)
