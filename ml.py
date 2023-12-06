#!/usr/bin/python

import math
import os
import sys
from argparse import ArgumentParser
from multiprocessing import Process
from subprocess import PIPE, Popen
from time import sleep, time

from mininet.cli import CLI
from mininet.link import Link, TCIntf, TCLink
from mininet.log import debug, info, lg
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.topo import Topo
from mininet.util import dumpNodeConnections
from monitor import monitor_qlen

time=3
N_j = 2
j_cmd=[
  "ping %s -s 500 -i 1 -c 1 >> %s; sleep 0.1s;",
  "ping %s -s 500 -i 1 -c 1 >> %s; sleep 0.1s;",
  "ping %s -s 500 -i 1 -c 1 >> %s; sleep 0.1s;",
  "ping %s -s 500 -i 1 -c 1 >> %s; sleep 0.1s;",
  "iperf -c %s -i 1 -t 30 -p 6000 -P 1 >> %s;",
]
j_repeat=[300,300,300,300,1,]

parser = ArgumentParser(description="Bufferbloat tests")
parser.add_argument('--bw-host',
                    '-B',
                    type=float,
                    help="Bandwidth of host links (Mb/s)",
                    default=1)

parser.add_argument('--bw-net',
                    '-b',
                    type=float,
                    help="Bandwidth of bottleneck (network) link (Mb/s)",
                    required=True)

parser.add_argument('--delay',
                    type=int,
                    help="Link propagation delay (ms)",
                    required=True)

parser.add_argument('--dir',
                    '-d',
                    help="Directory to store outputs",
                    required=True)

parser.add_argument('--time',
                    '-t',
                    help="Duration (sec) to run the experiment",
                    type=int,
                    default=10)

parser.add_argument('--maxq',
                    type=int,
                    help="Max buffer size of network interface in packets",
                    default=100)

parser.add_argument('--iperf_port',
                    type=int,
                    help="Port to use for iperf flows",
                    default=6000)
# TODO: include more parser parameters to pass pie/nopie argument
# and num_flows argument from run.sh

parser.add_argument('--if_pie',
                    type=bool,
                    help="Whether to use pie",
                    default=False)

parser.add_argument('--num_flows',
                    type=int,
                    help="Number of flows",
                    default=1)

# Linux uses CUBIC-TCP by default that doesn't have the usual sawtooth
# behaviour.  For those who are curious, invoke this script with
# --cong cubic and see what happens...
# sysctl -a | grep cong should list some interesting parameters.
parser.add_argument('--cong',
                    help="Congestion control algorithm to use",
                    default="reno")

# Expt parameters
args = parser.parse_args()
print(args)


class BasicIntf(TCIntf):
  """An interface with TSO and GSO disabled."""

  def config(self, **params):
    result = super(BasicIntf, self).config(**params)

    self.cmd('ethtool -K %s tso off gso off' % self)

    return result


class PIEIntf(BasicIntf):
  """An interface that runs the Proportional Integral controller-Enhanced AQM
  Algorithm. See the man page for info about paramaters:
  http://man7.org/linux/man-pages/man8/tc-pie.8.html."""

  def config(self, limit=1000, target="20ms", **params):
    result = super(PIEIntf, self).config(**params)

    cmd = ('%s qdisc add dev %s' + result['parent'] + 'handle 11: pie' +
           ' limit ' + str(limit) + ' target ' + target)
    parent = ' parent 10:1 '

    debug("adding pie w/cmd: %s\n" % cmd)
    tcoutput = self.tc(cmd)
    if tcoutput != '':
      error("*** Error: %s" % tcoutput)
    debug("cmd:", cmd, '\n')
    debug("output:", tcoutput, '\n')
    result['tcoutputs'].append(tcoutput)
    result['parent'] = parent

    return result


class AQMLink(Link):
  """A link that runs an AQM scheme on 0-2 of its interfaces."""

  def __init__(self,
               node1,
               node2,
               port1=None,
               port2=None,
               intfName1=None,
               intfName2=None,
               cls1=TCIntf,
               cls2=TCIntf,
               **params):
    super(AQMLink, self).__init__(node1,
                                  node2,
                                  port1=port1,
                                  port2=port2,
                                  intfName1=intfName1,
                                  intfName2=intfName2,
                                  cls1=cls1,
                                  cls2=cls2,
                                  params1=params,
                                  params2=params)


class BBTopo(Topo):
  "Simple topology for bufferbloat experiment."

  def __init__(self, n=2):
    super(BBTopo, self).__init__()

    s0 = self.addSwitch('s0')
    s1 = self.addSwitch('s1')
    _delay = '%dms' % args.delay
    _delay0 = '%dms' % 0

    for i in range(len(j_cmd)):
      h = self.addHost('h'+str(i))
      self.addLink(h, s0, cls1=BasicIntf, cls2=BasicIntf, bw=args.bw_host, delay=_delay, max_queue_size=args.maxq)
      hd = self.addHost('hd'+str(i))
      self.addLink(hd, s1, cls1=BasicIntf, cls2=BasicIntf, bw=args.bw_host, delay=_delay, max_queue_size=args.maxq)
    self.addLink(s0, s1, cls1=BasicIntf, cls2=BasicIntf, bw=args.bw_net, delay=_delay, max_queue_size=args.maxq)
    return

# Simple wrappers around monitoring utilities.  You are welcome to
# contribute neatly written (using classes) monitoring scripts for
# Mininet!
def start_tcpprobe(outfile="cwnd.txt"):
  Popen("sudo perf trace --no-syscalls --event 'tcp:tcp_probe' 2> %s" % (outfile), shell=True)


def stop_tcpprobe():
  Popen("killall -9 perf", shell=True).wait()


# Queue monitoring
def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
  monitor = Process(target=monitor_qlen, args=(iface, interval_sec, outfile))
  monitor.start()
  return monitor

iperf_port = 6000

def start_webserver(net):
  hd = net.getNodeByName('hd4')
  proc = hd.popen("python http/webserver.py", shell=True)
  hd.popen("iperf -s -w 1m -p %d" % (iperf_port))
  sleep(1)
  return [proc]


def start_ping(net, outfile="ping.txt"):
  # TODO: Start a ping train from h1 to h2 (or h2 to h1, does it
  # matter?)  Measure RTTs every 0.1 second.  Read the ping man page
  # to see how to do this.
  #
  # Hint: Use host.popen(cmd, shell=True).  If you pass shell=True
  # to popen, you can redirect cmd's output using shell syntax.
  # i.e. ping ... > /path/to/ping.
  # Hint: Use -i 0.1 in ping to ping every 0.1 sec
  '''
  h1 = net.getNodeByName('h1')
  h2 = net.getNodeByName('h2')
  '''


  for i in range(len(j_cmd)):
    hd = net.getNodeByName('hd'+str(i))
    one_cmd = j_cmd[i] % (hd.IP(), "ping" + str(i) + ".txt")
    total_cmd = ''
    for j in range(j_repeat[i]):
      total_cmd = total_cmd + one_cmd
    net.getNodeByName('h'+str(i)).popen(total_cmd, shell=True)
  '''
  total_cmd = j_cmd[1] % (hd.IP(), "ping2.txt")
  total_cmd = total_cmd + total_cmd
  h2.popen(total_cmd, shell=True)
  '''

def bufferbloat():
  if not os.path.exists(args.dir):
    os.makedirs(args.dir)
  os.system("sysctl -w net.ipv4.tcp_congestion_control=%s" % args.cong)
  topo = BBTopo()
  net = Mininet(topo=topo, host=CPULimitedHost, link=AQMLink)
  net.start()

  dumpNodeConnections(net.hosts)

  # This performs a basic all pairs ping test.
  net.pingAll()

  # Start all the monitoring processes
  start_tcpprobe("%s/cwnd.txt" % (args.dir))

  # TODO: Start monitoring the queue sizes.  Use the routine start_qmon
  # for this. Since the switch I created is "s0",
  # I monitor one of the interfaces.  Which interface?
  # The interface numbering starts with 1 and increases.
  # Depending on the order you add links to your network, this
  # number may be 1 or 2.  Ensure you use the correct number.
  qmon = start_qmon('s0-eth2', outfile="%s/q.txt" % (args.dir))

  # TODO: Start iperf, webservers, ping.
  #start_iperf(net)
  start_webserver(net)
  start_ping(net, outfile="ping.txt")

  '''
  # TODO: measure the time it takes to complete webpage transfer
  # from h1 to h2 (say) 3 times.  Hint: check what the following
  # command does: curl -o /dev/null -s -w %{time_total} google.com
  # Now use the curl command to fetch webpage from the webserver you
  # spawned on host h1 (not from google!)
  # Hint: Where is the webserver located?
  h1 = net.getNodeByName('h1')
  h2 = net.getNodeByName('h2')
  
  # Hint: have a separate function to do this and you may find the
  # loop below useful.
  i=0
  delta=[0,0,0]
  while i<3:
    start_time = time()
    # do the measurement (say) 3 times.
    h1.cmd("curl -o index_output.html -s %s:%s/index.html" % (h2.IP(), args.iperf_port))
    now = time()
    delta[i] = now - start_time

    if delta[i] > args.time:
      break 
    print("%.1fs left..." % (args.time - delta[i]))
    i = i + 1

  # TODO: compute average (and standard deviation) of the fetch
  # times.  You don't need to plot them.  Just note it in your
  # README and explain.
  avg = 0#stat.mean(delta)
  std = 0#stat.stdev(delta)
  print(avg, std)
  print('sgdfdsf')
  '''
  sleep(args.time+30)

  stop_tcpprobe()
  qmon.terminate()
  net.stop()
  # Ensure that all processes you create within Mininet are killed.
  # Sometimes they require manual killing.
  Popen("pgrep -f webserver.py | xargs kill -9", shell=True).wait()


if __name__ == "__main__":
  bufferbloat()
