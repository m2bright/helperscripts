#!/bin/sh

add_ssh_keys

function add_ssh_keys() {
  count=`ssh-add -l |grep -v "The agent" |wc -l|awk '{print $1}'`
  if [ "0" == "${count}" ]
  then
    arr=`cd ~/.ssh && ls *.key`
    for key in ${arr[@]}
    do
      ssh-add -k ~/.ssh/${key}
    done
  fi
}
