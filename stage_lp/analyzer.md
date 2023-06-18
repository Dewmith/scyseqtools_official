---
title: Description of the analyzer
author: L. Pezard
---


## Struture of the analyzer

The analyzer is built on a client / server architecture. It is supposed to propose (some of) the `scikits-symbolic` procedures via a webservice server based on [Ladon](https://pypi.org/project/ladon/) library **Is it the right technique? Is Ladon still maintained?**. (see also [jsonwspclient](https://pypi.org/project/jsonwspclient/) for a client in replacement of Ladon client side).
**Is there any _standard_ to change Ladon?**
Using [Requests](https://requests.readthedocs.io/en/latest/)? Or REST?

