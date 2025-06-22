# massa_acheta_docker/app_config.py
app_config = {}
app_config['telegram']  = {}
app_config['service']   = {}
app_config['alerts']    = {}

# --- Version ---
app_config['config_version'] = "1.1"

# Telegram settings
app_config['telegram']['sending_delay_sec'] = 2
app_config['telegram']['sending_timeout_sec'] = 5

# Service settings
app_config['service']['results_path'] = "app_results.json"
app_config['service']['deferred_credits_path'] = "deferred_credits.json"
app_config['service']['stat_path'] = "app_stat.json"

app_config['service']['main_loop_period_min'] = 10
app_config['service']['heartbeat_period_hours'] = 6
app_config['service']['massa_network_update_period_min'] = 30

app_config['service']['http_session_timeout_sec'] = 300
app_config['service']['http_probe_timeout_sec'] = 120

app_config['service']['massa_release_url'] = "https://api.github.com/repos/massalabs/massa/releases/latest"
app_config['service']['acheta_release_url'] = "https://api.github.com/repos/COLOC-BOB/Massa_acheta_docker/releases/latest"

app_config['service']['mainnet_rpc_url'] = "https://mainnet.massa.net/api/v2"
app_config['service']['mainnet_explorer_url'] = "https://explorer.massa.net/mainnet"
app_config['service']['massexplo_api_url'] = "https://api.massexplo.io/info?network=MainNet"
app_config['service']['mainnet_stakers_bundle'] = 100

# Alert settings (centralisé pour alert_manager)
app_config['alerts']['wallet_balance_drop_threshold'] = 10   # ex: 10 MAS
app_config['alerts']['min_peers'] = 5
app_config['alerts']['alert_cooldown_sec'] = 180
app_config['alerts']['heartbeat_enabled'] = True
app_config['alerts']['releases_enabled'] = True
