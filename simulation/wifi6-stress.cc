/*
 * Wi-Fi 6 (IEEE 802.11ax) Stress Simulation Scenario
 * Author: Antigravity Assistant & Senior Simulation Engineer
 *
 * Implements a parameterized Wi-Fi 6 (or Wi-Fi 5 baseline) infrastructure BSS:
 *  - 1 AP at (0, 0, 0), N STAs equidistant on a circle of radius R.
 *  - Uplink UDP traffic from STAs to AP with SeqTsHeader timestamping.
 *  - Explicit warm-up interval before active traffic window.
 *  - Deterministic CSV output: per-flow metrics and run summary.
 *  - Exact P95 tail latency computation from packet-level delays.
 */

#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/data-rate.h"
#include "ns3/double.h"
#include "ns3/flow-monitor-helper.h"
#include "ns3/flow-monitor.h"
#include "ns3/internet-stack-helper.h"
#include "ns3/ipv4-address-helper.h"
#include "ns3/ipv4-flow-classifier.h"
#include "ns3/log.h"
#include "ns3/mobility-helper.h"
#include "ns3/neighbor-cache-helper.h"
#include "ns3/packet.h"
#include "ns3/rng-seed-manager.h"
#include "ns3/seq-ts-header.h"
#include "ns3/ssid.h"
#include "ns3/string.h"
#include "ns3/udp-client-server-helper.h"
#include "ns3/udp-server.h"
#include "ns3/uinteger.h"
#include "ns3/wifi-helper.h"
#include "ns3/wifi-static-setup-helper.h"
#include "ns3/yans-wifi-channel.h"
#include "ns3/yans-wifi-helper.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("Wifi6Stress");

// Global metrics tracker
struct FlowTracker
{
    uint32_t staId{0};
    std::string srcIp{""};
    std::string dstIp{""};
    uint64_t txPackets{0};
    uint64_t txBytes{0};
    uint64_t rxPackets{0};
    uint64_t rxBytes{0};
    std::vector<double> packetDelaysMs; // collected during measurement window
};

static std::vector<FlowTracker> g_flowTrackers;
static double g_warmupTime = 1.0;
static double g_activeTime = 1.0;

void
OnClientTx(uint32_t staId, Ptr<const Packet> packet, const Address& src, const Address& dst)
{
    // Record only packets transmitted during active window
    Time now = Simulator::Now();
    if (now >= Seconds(g_warmupTime) && now <= Seconds(g_warmupTime + g_activeTime + 0.0001))
    {
        g_flowTrackers[staId].txPackets++;
        g_flowTrackers[staId].txBytes += packet->GetSize();
    }
}

void
OnServerRx(uint32_t staId, Ptr<const Packet> packet, const Address& from, const Address& to)
{
    Ptr<Packet> copy = packet->Copy();
    SeqTsHeader seqTs;
    if (copy->RemoveHeader(seqTs))
    {
        Time txTime = seqTs.GetTs();
        Time rxTime = Simulator::Now();
        // Check if transmission originated during the measurement window
        if (txTime >= Seconds(g_warmupTime) && txTime <= Seconds(g_warmupTime + g_activeTime + 0.0001))
        {
            Time delay = rxTime - txTime;
            double delayMs = delay.GetSeconds() * 1000.0;
            g_flowTrackers[staId].rxPackets++;
            g_flowTrackers[staId].rxBytes += copy->GetSize(); // payload bytes without SeqTsHeader
            g_flowTrackers[staId].packetDelaysMs.push_back(delayMs);
        }
    }
}

int
main(int argc, char* argv[])
{
    uint32_t nStations = 5;
    std::string standard = "80211ax";
    uint32_t channelWidth = 20;
    uint32_t mcs = 3;
    std::string dataRateStr = "2Mbps";
    uint32_t payloadSize = 1000;
    double warmupTime = 1.0;
    double activeTime = 1.0;
    double drainTime = 0.1;
    double radius = 5.0;
    uint32_t seed = 1;
    uint32_t run = 1;
    std::string outputDir = "data/raw";
    std::string runId = "pilot_1";

    CommandLine cmd(__FILE__);
    cmd.AddValue("nStations", "Number of non-AP stations", nStations);
    cmd.AddValue("standard", "Wi-Fi standard: 80211ax or 80211ac", standard);
    cmd.AddValue("channelWidth", "Channel width in MHz (20, 40, 80)", channelWidth);
    cmd.AddValue("mcs", "Modulation and Coding Scheme (0 to 11)", mcs);
    cmd.AddValue("dataRate", "Offered UDP data rate per station (e.g. 2Mbps)", dataRateStr);
    cmd.AddValue("payloadSize", "Application payload size in bytes", payloadSize);
    cmd.AddValue("warmupTime", "Warm-up period before measurement in seconds", warmupTime);
    cmd.AddValue("activeTime", "Active measurement window duration in seconds", activeTime);
    cmd.AddValue("drainTime", "Post-traffic drain time in seconds to allow in-flight packets to clear", drainTime);
    cmd.AddValue("radius", "Radius of stations around AP in meters", radius);
    cmd.AddValue("seed", "RNG seed", seed);
    cmd.AddValue("run", "RNG run number", run);
    cmd.AddValue("outputDir", "Directory to write CSV results", outputDir);
    cmd.AddValue("runId", "Identifier for this simulation run", runId);
    cmd.Parse(argc, argv);

    g_warmupTime = warmupTime;
    g_activeTime = activeTime;
    g_flowTrackers.resize(nStations);
    for (uint32_t i = 0; i < nStations; ++i)
    {
        g_flowTrackers[i].staId = i;
    }

    // Configure RNG
    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);

    // Calculate packet transmission interval from offered rate
    DataRate offeredDataRate(dataRateStr);
    double bitsPerPacket = (payloadSize + 12) * 8.0; // including SeqTsHeader
    Time packetInterval = Seconds(bitsPerPacket / offeredDataRate.GetBitRate());

    // Create Nodes
    NodeContainer wifiApNode;
    wifiApNode.Create(1);

    NodeContainer wifiStaNodes;
    wifiStaNodes.Create(nStations);

    // Channel and PHY configuration
    auto channelHelper = YansWifiChannelHelper::Default();
    auto channel = channelHelper.Create();

    YansWifiPhyHelper phy;
    phy.SetPcapDataLinkType(WifiPhyHelper::DLT_IEEE802_11_RADIO);
    phy.SetChannel(channel);

    WifiHelper wifi;
    std::string dataMode;
    std::string ctrlMode;
    std::string channelStr = "{0, " + std::to_string(channelWidth) + ", BAND_5GHZ, 0}";

    if (standard == "80211ax")
    {
        wifi.SetStandard(WIFI_STANDARD_80211ax);
        dataMode = "HeMcs" + std::to_string(mcs);
        ctrlMode = "OfdmRate24Mbps";
        wifi.ConfigHeOptions("GuardInterval", TimeValue(NanoSeconds(800)));
    }
    else if (standard == "80211ac")
    {
        wifi.SetStandard(WIFI_STANDARD_80211ac);
        dataMode = "VhtMcs" + std::to_string(mcs);
        ctrlMode = "OfdmRate24Mbps";
    }
    else
    {
        NS_FATAL_ERROR("Unsupported standard: " << standard);
    }

    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode", StringValue(dataMode),
                                 "ControlMode", StringValue(ctrlMode));
    phy.Set("ChannelSettings", StringValue(channelStr));

    // MAC setup
    WifiMacHelper mac;
    Ssid ssid = Ssid("wifi-stress-" + standard);

    mac.SetType("ns3::StaWifiMac",
                "Ssid", SsidValue(ssid),
                "MpduBufferSize", UintegerValue(64));
    NetDeviceContainer staDevices = wifi.Install(phy, mac, wifiStaNodes);

    mac.SetType("ns3::ApWifiMac",
                "EnableBeaconJitter", BooleanValue(false),
                "Ssid", SsidValue(ssid));
    NetDeviceContainer apDevice = wifi.Install(phy, mac, wifiApNode);

    // Static association setup for deterministic baseline startup
    auto apDev = DynamicCast<WifiNetDevice>(apDevice.Get(0));
    WifiStaticSetupHelper::SetStaticAssociation(apDev, staDevices);
    WifiStaticSetupHelper::SetStaticBlockAck(apDev, staDevices, {0});

    // Mobility
    MobilityHelper mobility;
    Ptr<ListPositionAllocator> positionAlloc = CreateObject<ListPositionAllocator>();
    positionAlloc->Add(Vector(0.0, 0.0, 0.0)); // AP position

    const double pi = 3.14159265358979323846;
    for (uint32_t i = 0; i < nStations; ++i)
    {
        double angle = 2.0 * pi * i / nStations;
        double x = radius * std::cos(angle);
        double y = radius * std::sin(angle);
        positionAlloc->Add(Vector(x, y, 0.0));
    }
    mobility.SetPositionAllocator(positionAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(wifiApNode);
    mobility.Install(wifiStaNodes);

    // Network & IP Stack
    InternetStackHelper stack;
    stack.Install(wifiApNode);
    stack.Install(wifiStaNodes);

    Ipv4AddressHelper address;
    address.SetBase("192.168.1.0", "255.255.255.0");
    Ipv4InterfaceContainer staInterfaces = address.Assign(staDevices);
    Ipv4InterfaceContainer apInterface = address.Assign(apDevice);

    NeighborCacheHelper nbCache;
    nbCache.PopulateNeighborCache();

    // Applications: UdpServer on AP, UdpClient on each STA
    double simStopTime = warmupTime + activeTime + drainTime; // allow in-flight packets to clear

    for (uint32_t i = 0; i < nStations; ++i)
    {
        uint16_t port = 5000 + i;

        // Server on AP
        UdpServerHelper server(port);
        ApplicationContainer serverApp = server.Install(wifiApNode.Get(0));
        serverApp.Start(Seconds(0.0));
        serverApp.Stop(Seconds(simStopTime));

        // Trace server reception with exact timestamps
        Ptr<UdpServer> udpServer = DynamicCast<UdpServer>(serverApp.Get(0));
        udpServer->TraceConnectWithoutContext(
            "RxWithAddresses",
            MakeBoundCallback(&OnServerRx, i));

        // Client on STA i
        UdpClientHelper client(apInterface.GetAddress(0), port);
        client.SetAttribute("MaxPackets", UintegerValue(0xFFFFFFFFU));
        client.SetAttribute("Interval", TimeValue(packetInterval));
        client.SetAttribute("PacketSize", UintegerValue(payloadSize));

        ApplicationContainer clientApp = client.Install(wifiStaNodes.Get(i));
        clientApp.Start(Seconds(warmupTime));
        clientApp.Stop(Seconds(warmupTime + activeTime));

        // Trace client transmission
        Ptr<UdpClient> udpClient = DynamicCast<UdpClient>(clientApp.Get(0));
        udpClient->TraceConnectWithoutContext(
            "TxWithAddresses",
            MakeBoundCallback(&OnClientTx, i));

        std::ostringstream ossSrc;
        ossSrc << staInterfaces.GetAddress(i);
        g_flowTrackers[i].srcIp = ossSrc.str();

        std::ostringstream ossDst;
        ossDst << apInterface.GetAddress(0);
        g_flowTrackers[i].dstIp = ossDst.str();
    }

    // Install FlowMonitor for independent verification
    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    // Run Simulation
    Simulator::Stop(Seconds(simStopTime));
    Simulator::Run();

    monitor->CheckForLostPackets();
    uint64_t flowMonLostPackets = 0;
    for (const auto& flow : monitor->GetFlowStats())
    {
        flowMonLostPackets += flow.second.lostPackets;
    }
    Simulator::Destroy();

    // Calculate Metrics
    std::filesystem::create_directories(outputDir);

    std::string flowMetricsPath = outputDir + "/" + runId + "_flow_metrics.csv";
    std::string summaryMetricsPath = outputDir + "/" + runId + "_summary.csv";
    std::string manifestPath = outputDir + "/" + runId + "_manifest.json";

    std::ofstream flowOut(flowMetricsPath);
    if (!flowOut.is_open())
    {
        NS_FATAL_ERROR("Cannot open flow output file: " << flowMetricsPath);
    }

    flowOut << "run_id,seed,run,standard,n_stations,channel_width_mhz,mcs,offered_rate_kbps,"
            << "payload_size,warmup_s,active_window_s,flow_id,src_ip,dst_ip,tx_packets,"
            << "rx_packets,tx_bytes,rx_bytes,mean_delay_ms,p95_delay_ms,pdr_percent,goodput_mbps\n";

    uint64_t totalTxPackets = 0;
    uint64_t totalRxPackets = 0;
    uint64_t totalTxBytes = 0;
    uint64_t totalRxBytes = 0;
    std::vector<double> allDelaysMs;
    std::vector<double> stationGoodputs;

    for (uint32_t i = 0; i < nStations; ++i)
    {
        FlowTracker& ft = g_flowTrackers[i];
        totalTxPackets += ft.txPackets;
        totalRxPackets += ft.rxPackets;
        totalTxBytes += ft.txBytes;
        totalRxBytes += ft.rxBytes;

        double meanDelayMs = 0.0;
        double p95DelayMs = 0.0;

        if (!ft.packetDelaysMs.empty())
        {
            double sumDelay = std::accumulate(ft.packetDelaysMs.begin(), ft.packetDelaysMs.end(), 0.0);
            meanDelayMs = sumDelay / ft.packetDelaysMs.size();

            std::sort(ft.packetDelaysMs.begin(), ft.packetDelaysMs.end());
            size_t idx95 = static_cast<size_t>(std::ceil(0.95 * ft.packetDelaysMs.size())) - 1;
            if (idx95 >= ft.packetDelaysMs.size())
            {
                idx95 = ft.packetDelaysMs.size() - 1;
            }
            p95DelayMs = ft.packetDelaysMs[idx95];

            allDelaysMs.insert(allDelaysMs.end(), ft.packetDelaysMs.begin(), ft.packetDelaysMs.end());
        }

        double pdr = (ft.txPackets > 0) ? (100.0 * ft.rxPackets / ft.txPackets) : 0.0;
        double goodputMbps = (ft.rxBytes * 8.0) / (activeTime * 1e6);
        stationGoodputs.push_back(goodputMbps);

        flowOut << runId << "," << seed << "," << run << "," << standard << "," << nStations << ","
                << channelWidth << "," << mcs << "," << (offeredDataRate.GetBitRate() / 1000) << ","
                << payloadSize << "," << warmupTime << "," << activeTime << "," << (i + 1) << ","
                << ft.srcIp << "," << ft.dstIp << "," << ft.txPackets << "," << ft.rxPackets << ","
                << ft.txBytes << "," << ft.rxBytes << "," << std::fixed << std::setprecision(4)
                << meanDelayMs << "," << p95DelayMs << "," << std::setprecision(2) << pdr << ","
                << std::setprecision(4) << goodputMbps << "\n";
    }
    flowOut.close();

    // Aggregate calculations
    double aggregateGoodputMbps = (totalRxBytes * 8.0) / (activeTime * 1e6);
    double aggregatePdr = (totalTxPackets > 0) ? (100.0 * totalRxPackets / totalTxPackets) : 0.0;
    double overallMeanDelayMs = 0.0;
    double overallP95DelayMs = 0.0;

    if (!allDelaysMs.empty())
    {
        double totalDelay = std::accumulate(allDelaysMs.begin(), allDelaysMs.end(), 0.0);
        overallMeanDelayMs = totalDelay / allDelaysMs.size();

        std::sort(allDelaysMs.begin(), allDelaysMs.end());
        size_t globalIdx95 = static_cast<size_t>(std::ceil(0.95 * allDelaysMs.size())) - 1;
        if (globalIdx95 >= allDelaysMs.size())
        {
            globalIdx95 = allDelaysMs.size() - 1;
        }
        overallP95DelayMs = allDelaysMs[globalIdx95];
    }

    // Jain's Fairness Index = (sum(x_i))^2 / (n * sum(x_i^2))
    double sumX = 0.0;
    double sumXsq = 0.0;
    for (double x : stationGoodputs)
    {
        sumX += x;
        sumXsq += (x * x);
    }
    double jainFairness = 0.0;
    if (sumXsq > 0.0 && nStations > 0)
    {
        jainFairness = (sumX * sumX) / (nStations * sumXsq);
    }

    // Summary CSV
    std::ofstream sumOut(summaryMetricsPath);
    if (!sumOut.is_open())
    {
        NS_FATAL_ERROR("Cannot open summary output file: " << summaryMetricsPath);
    }

    sumOut << "run_id,seed,run,standard,n_stations,channel_width_mhz,mcs,offered_rate_kbps,"
           << "payload_size,warmup_s,active_window_s,total_tx_packets,total_rx_packets,"
           << "total_tx_bytes,total_rx_bytes,aggregate_goodput_mbps,aggregate_pdr_percent,"
           << "mean_delay_ms,p95_delay_ms,jain_fairness_index\n";

    sumOut << runId << "," << seed << "," << run << "," << standard << "," << nStations << ","
           << channelWidth << "," << mcs << "," << (offeredDataRate.GetBitRate() / 1000) << ","
           << payloadSize << "," << warmupTime << "," << activeTime << "," << totalTxPackets << ","
           << totalRxPackets << "," << totalTxBytes << "," << totalRxBytes << ","
           << std::fixed << std::setprecision(4) << aggregateGoodputMbps << ","
           << std::setprecision(2) << aggregatePdr << "," << std::setprecision(4)
           << overallMeanDelayMs << "," << overallP95DelayMs << "," << std::setprecision(4)
           << jainFairness << "\n";
    sumOut.close();

    // Manifest JSON
    std::ofstream manOut(manifestPath);
    if (manOut.is_open())
    {
        manOut << "{\n"
               << "  \"run_id\": \"" << runId << "\",\n"
               << "  \"ns3_version\": \"3.49\",\n"
               << "  \"standard\": \"" << standard << "\",\n"
               << "  \"n_stations\": " << nStations << ",\n"
               << "  \"channel_width_mhz\": " << channelWidth << ",\n"
               << "  \"mcs\": " << mcs << ",\n"
               << "  \"offered_rate\": \"" << dataRateStr << "\",\n"
               << "  \"payload_size_bytes\": " << payloadSize << ",\n"
               << "  \"warmup_time_s\": " << warmupTime << ",\n"
               << "  \"active_time_s\": " << activeTime << ",\n"
               << "  \"drain_time_s\": " << drainTime << ",\n"
               << "  \"seed\": " << seed << ",\n"
               << "  \"run\": " << run << ",\n"
               << "  \"aggregate_goodput_mbps\": " << aggregateGoodputMbps << ",\n"
               << "  \"aggregate_pdr_percent\": " << aggregatePdr << ",\n"
               << "  \"overall_mean_delay_ms\": " << overallMeanDelayMs << ",\n"
               << "  \"overall_p95_delay_ms\": " << overallP95DelayMs << ",\n"
               << "  \"jain_fairness_index\": " << jainFairness << ",\n"
               << "  \"total_tx_packets\": " << totalTxPackets << ",\n"
               << "  \"total_rx_packets\": " << totalRxPackets << ",\n"
               << "  \"undelivered_packets\": " << (totalTxPackets - totalRxPackets) << ",\n"
               << "  \"flowmon_lost_packets\": " << flowMonLostPackets << "\n"
               << "}\n";
        manOut.close();
    }

    std::cout << "[Wifi6Stress] Run " << runId << " complete: "
              << "Goodput=" << aggregateGoodputMbps << " Mbps, "
              << "PDR=" << aggregatePdr << "%, "
              << "MeanDelay=" << overallMeanDelayMs << " ms, "
              << "P95Delay=" << overallP95DelayMs << " ms, "
              << "Jain=" << jainFairness << ", "
              << "Undelivered=" << (totalTxPackets - totalRxPackets) << ", "
              << "FlowMonLost=" << flowMonLostPackets << "\n";

    return 0;
}
