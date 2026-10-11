
#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import OVSSwitch, OVSBridge
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def create_topology():

    info("*** Creating Mininet network\n")

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        build=False
    )

    # --------------------------------------------------
    # 1. DATA-PLANE HOSTS
    # --------------------------------------------------

    info("*** Adding data-plane hosts\n")

    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h3 = net.addHost('h3', ip='10.0.0.3/24')
    h4 = net.addHost('h4', ip='10.0.0.4/24')

    # --------------------------------------------------
    # 2. DATA-PLANE SWITCHES
    # Temporary standalone/STP configuration for testing.
    # Ryu integration will be configured later.
    # --------------------------------------------------

    info("*** Adding three data-plane switches\n")

    s1 = net.addSwitch(
        's1',
        protocols='OpenFlow13',
        failMode='standalone',
        stp=True
    )

    s2 = net.addSwitch(
        's2',
        protocols='OpenFlow13',
        failMode='standalone',
        stp=True
    )

    s3 = net.addSwitch(
        's3',
        protocols='OpenFlow13',
        failMode='standalone',
        stp=True
    )

    # --------------------------------------------------
    # 3. DATA-PLANE HOST LINKS
    # --------------------------------------------------

    info("*** Connecting data-plane hosts\n")

    # s1 port 1 -> h1; s1 port 2 -> h2
    net.addLink(h1, s1, port2=1)
    net.addLink(h2, s1, port2=2)

    # s2 port 1 -> h3
    net.addLink(h3, s2, port2=1)

    # s3 port 1 -> h4
    net.addLink(h4, s3, port2=1)

    # --------------------------------------------------
    # 4. DATA-PLANE SWITCH LINKS
    # --------------------------------------------------

    info("*** Connecting data-plane switches\n")

    # Alternate path: s1 port 3 <-> s2 port 2
    net.addLink(
        s1, s2,
        port1=3,
        port2=2,
        cls=TCLink,
        bw=100
    )

    # Alternate path: s2 port 3 <-> s3 port 2
    net.addLink(
        s2, s3,
        port1=3,
        port2=2,
        cls=TCLink,
        bw=100
    )

    # Direct path: s1 port 4 <-> s3 port 3
    net.addLink(
        s1, s3,
        port1=4,
        port2=3,
        cls=TCLink,
        bw=5
    )

    # --------------------------------------------------
    # 5. SEPARATE MANAGEMENT NETWORK
    # s4 is a management-only bridge.
    # It does not change the ports on s1, s2 or s3.
    # --------------------------------------------------

    info("*** Adding management network\n")

    s4 = net.addSwitch('s4', cls=OVSBridge)

    # Temporary local monitoring endpoint for testing.
    # This is NOT Person 2's real monitoring server.
    mon = net.addHost(
        'mon',
        ip='192.168.100.254/24'
    )

    # Each host receives a second interface named eth1.
    # Management switch ports 1-4 connect h1-h4.
    net.addLink(
        h1, s4,
        intfName1='h1-eth1',
        port2=1
    )

    net.addLink(
        h2, s4,
        intfName1='h2-eth1',
        port2=2
    )

    net.addLink(
        h3, s4,
        intfName1='h3-eth1',
        port2=3
    )

    net.addLink(
        h4, s4,
        intfName1='h4-eth1',
        port2=4
    )

    # Management switch port 5 -> temporary monitor
    net.addLink(mon, s4, port2=5)

    # --------------------------------------------------
    # 6. BUILD AND START
    # --------------------------------------------------

    info("*** Building network\n")
    net.build()

    info("*** Starting network\n")
    net.start()

    # Assign management IPs after interfaces exist.
    management_addresses = [
        (h1, 'h1-eth1', '192.168.100.11'),
        (h2, 'h2-eth1', '192.168.100.12'),
        (h3, 'h3-eth1', '192.168.100.13'),
        (h4, 'h4-eth1', '192.168.100.14'),
    ]

    info("*** Configuring management IP addresses\n")

    for host, interface, address in management_addresses:
        result = host.cmd(
            f'ip addr add {address}/24 dev {interface}'
        )

        if result:
            info(
                f"*** WARNING: Check {interface} on {host.name}\n"
            )
        else:
            info(
                f"*** {host.name} management IP: {address}\n"
            )

    info("*** Network started\n")
    info("*** Use 'net' to inspect links\n")
    info("*** Use 'links' to inspect link status\n")
    info("*** Use 'h1 ping -c 3 10.0.0.4' for data-plane testing\n")
    info("*** Use 'h1 ping -c 3 192.168.100.254' for management testing\n")
    info("*** Avoid 'pingall' because the temporary monitor is on a separate subnet\n")

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
