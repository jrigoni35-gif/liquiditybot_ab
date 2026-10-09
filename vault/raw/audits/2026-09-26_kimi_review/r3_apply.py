"""Injection: drive R3 with a venue tier ABOVE config (the dangerous direction,
same shape as the one real OM-080 row seq 69754: actual 40/80), apply the
proposal's proposed_config_values verbatim to the repo config, run config_guard."""
import json, os, sys, copy, tempfile
sys.path.insert(0, os.getcwd())
from execution import order_manager as om_mod
from execution.order_manager import OrderManager
from core import config_guard
import core.audit as ca
td = tempfile.mkdtemp()
ca.configure_audit(os.path.join(td, "audit.jsonl"))
om_mod._FEE_PROPOSAL_REL_PATH = os.path.join(td, "latest_proposal.json")
cfg = json.load(open("config.json"))
act_m, act_t = float(sys.argv[1]), float(sys.argv[2])
class Feed:
    def has_private_credentials(self): return True
    def get_trade_fee_schedule(self, pairs):
        return {"pairs": {p: {"maker_bps": act_m, "taker_bps": act_t} for p in pairs},
                "volume_30d": 1.0, "volume_currency": "USD"}
omc = dict(cfg["order_manager"]); 
om = OrderManager(Feed(), omc, dry_run=True, pair_meta={"XXBTZUSD": {"price_decimals": 1}},
                  **({"pretrade_fee_bps": (cfg["pretrade"]["maker_fee_bps"], cfg["pretrade"]["taker_fee_bps"])} if "pretrade_fee_bps" in OrderManager.__init__.__code__.co_varnames else {}))
om.check_fee_reconciliation(now=1e9)
prop = json.load(open(om_mod._FEE_PROPOSAL_REL_PATH))
print("proposed:", prop["proposed_config_values"])
new = copy.deepcopy(cfg)
for k, v in prop["proposed_config_values"].items():
    a, b = k.split("."); new[a][b] = v
base = [f for f in config_guard.validate(cfg) if f[0] == "FATAL"]
after = [f for f in config_guard.validate(new) if f[0] == "FATAL"]
print("CONTROL fatal count (config as-is):", len(base))
print("after applying proposal fatal count:", len(after))
for f in after: print("  ", f[1][:260])
