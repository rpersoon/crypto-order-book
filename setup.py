# Copyright (c) 2017 - 2019 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


from setuptools import setup

setup(
   name='crypto_order_book',
   version='1.0.1',
   description='Cryptocurrency exchange order book',
   author='Ricardo Persoon',
   packages=['crypto_order_book'],
   install_requires=[
      # We need to pin sortedcontainers to a 1.x version, as an incompatible and unfinished 2.x version was released
      # that is still missing functionality that we need
      'sortedcontainers==1.5.10',
      'websocket-client'
   ]
)
