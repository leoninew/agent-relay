from agent_relay.application.dto.preferences import ResolvedLanguage

_MESSAGES: dict[ResolvedLanguage, dict[str, str]] = {
    "zh-CN": {
        "exitTitle": "退出 Agent Relay",
        "exitBody": "确定要关闭管理端吗？",
        "startupFailed": "Agent Relay 启动失败。",
        "logFile": "日志文件",
        "offline": "管理端已离线。",
    },
    "en": {
        "exitTitle": "Exit Agent Relay",
        "exitBody": "Close the management app?",
        "startupFailed": "Agent Relay failed to start.",
        "logFile": "Log file",
        "offline": "The management app is offline.",
    },
}


def native_message(language: ResolvedLanguage, key: str) -> str:
    return _MESSAGES[language][key]
