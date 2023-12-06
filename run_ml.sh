#!/bin/bash

# Note: Mininet must be run as root.  So invoke this shell script
# using sudo.

# Solve a problem where cgroups does not start automatically
#service cgroup-lite restart 2>&1 > /dev/null

time=3
bwnet=10
bwhost=1000
# TODO: If you want the RTT to be 20ms what should the delay on each
# link be?  Set this value correctly.

iperf_port=6000

maxq=100
dir=.

# TODO: Add more parameters if needed
delay=20
if_pie=False
num_flows=1

mn -c
sudo python ml.py --bw-host $bwhost --bw-net $bwnet --iperf_port $iperf_port --maxq $maxq --dir $dir --time $time --delay $delay --if_pie $if_pie --num_flows $num_flows

# TODO: Ensure the input file names match the ones you use in
# bufferbloat.py script.  Also ensure the plot file names match
# the required naming convention when submitting your tarball.
python plot_tcpprobe.py -f $dir/cwnd.txt -o $dir/cwnd-iperf.png -p $iperf_port
python plot_queue.py -f $dir/q.txt -o $dir/q.png
python plot_ping.py -f $dir/ping.txt -o $dir/rtt.png
