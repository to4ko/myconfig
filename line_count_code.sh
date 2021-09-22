#!/bin/bash
find . -name '*.yaml' -type f -print0 | xargs -0 cat | sed '/^\s*#/d;/^\s*$/d' | wc -l