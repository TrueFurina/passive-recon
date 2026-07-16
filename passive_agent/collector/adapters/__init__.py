"""R7 四类集群适配器实现。

Web 集群：crt.sh(真实免凭证) + DNS(真实免凭证) + FOFA(凭证) + Subfinder(凭证) + Mock(回退)
公众号集群：WechatAdapter(凭证) + MockWA(回退)
小程序集群：MiniappAdapter(凭证) + MockMA(回退)
工商股权集群：EquityAdapter(凭证) + MockEQ(回退)
"""
from passive_agent.collector.adapters.crtsh_adapter import CrtshAdapter
from passive_agent.collector.adapters.dns_adapter import DnsAdapter
from passive_agent.collector.adapters.fofa_adapter import FofaAdapter
from passive_agent.collector.adapters.subfinder_adapter import SubfinderAdapter
from passive_agent.collector.adapters.wechat_adapter import WechatAdapter
from passive_agent.collector.adapters.miniapp_adapter import MiniappAdapter
from passive_agent.collector.adapters.equity_adapter import EquityAdapter
from passive_agent.collector.adapters.mock_adapter import MockAdapter

__all__ = [
    "CrtshAdapter",
    "DnsAdapter",
    "FofaAdapter",
    "SubfinderAdapter",
    "WechatAdapter",
    "MiniappAdapter",
    "EquityAdapter",
    "MockAdapter",
]
