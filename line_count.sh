#!/bin/bash
find . -name '*.yaml' -type f -print0 | xargs -0 cat | wc -l