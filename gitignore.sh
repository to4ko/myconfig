#!/bin/bash

cd /usr/share/hassio/homeassistant
echo "-----> cd done"
git rm -r --cached .
echo "-----> remove local cache"
git add .
echo "-----> add everything back"
git commit -m ".gitignore update"
echo "-----> commit it"
git push origin master
echo "-----> push it to remote"

exit
