from config.settings import load_config, check_config_file
from config.logger import setup_logging
from core.utils.util import get_local_ip, initialize_modules
from core.connection import ConnectionHandler
from core.agent.agent_manager import AgentManager
from core.utils.dialogue import Dialogue, Message
import asyncio
import uuid

logger = setup_logging()
config = load_config()

modules = initialize_modules(
            logger, config, True, True, True, True, True, True
        )

vad = modules["vad"]
asr = modules["asr"]
tts = modules["tts"]
llm = modules["llm"]
intent = modules["intent"]
memory = modules["memory"]

conn = ConnectionHandler(
            config,
            vad,
            asr,
            llm,
            tts,
            memory,
            intent,
        )
conn.session_id = str(uuid.uuid4())
conn.loop = asyncio.get_event_loop()
conn.headers = dict({})
private_config = conn._initialize_private_config()
conn._initialize_components(private_config)

agent_manager = AgentManager(conn)
asyncio.run(agent_manager.initialize_servers())

dialogue = Dialogue()
dialogue.put(Message(role="user", content="你好"))
conn.chat_with_agent_calling("你好", "script_murder")

