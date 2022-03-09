import logging
import pathlib
from logging.handlers import RotatingFileHandler

from telegram_log_handler import TelegramHandler

NOTIFICATION = 25


log_dir = pathlib.Path(__file__).parent.parent / 'log'
log_maxBytes = 30 * 1024 * 1024
log_backupCount = 3


if not log_dir.exists():
    log_dir.mkdir()


def notification(self, message, *args, **kws):
    if self.isEnabledFor(NOTIFICATION):
        self._log(NOTIFICATION, message, args, **kws)


logging.addLevelName(NOTIFICATION, "NOTIFICATION")
logging.Logger.notification = notification


def setup_logging(is_debug: bool = False, tg_bot_key: str = None, tg_chat_id: str = None):
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(log_dir / 'liquidator_bot.log', maxBytes=log_maxBytes, backupCount=log_backupCount),
    ]

    try:
        if tg_bot_key is not None and tg_chat_id is not None:
            telegram_handler = TelegramHandler(
                bot_token=tg_bot_key,
                chat_ids={"client": tg_chat_id},
                project_name="liquidator_bot",
            )
            telegram_handler.setLevel(NOTIFICATION)
            telegram_handler.setFormatter(
                logging.Formatter('%(asctime)-15s\n%(threadName)s\n%(levelname)-8s\n%(message)s')
            )
            handlers.append(telegram_handler)
    except Exception as e:
        pass

    logging.basicConfig(format='%(asctime)-15s %(threadName)s %(levelname)-8s %(message)s',
                        level=(logging.DEBUG if is_debug else logging.INFO), handlers=handlers)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)

    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger("web3").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("requests").setLevel(logging.INFO)


def setup_notificator(is_debug: bool = False, tg_bot_key: str = None, tg_chat_id: str = None):
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(log_dir / 'liquidator_bot.log', maxBytes=log_maxBytes, backupCount=log_backupCount),
    ]

    try:
        if tg_bot_key is not None and tg_chat_id is not None:
            telegram_handler = TelegramHandler(
                bot_token=tg_bot_key,
                chat_ids={"client": tg_chat_id},
                project_name="velero_notificator",
            )
            telegram_handler.setLevel(NOTIFICATION)
            handlers.append(telegram_handler)
            telegram_handler.setFormatter(logging.Formatter('%(asctime)-15s\n\n %(message)s'))
    except Exception as e:
        pass

    logging.basicConfig(format='%(asctime)-15s %(threadName)s %(levelname)-8s %(message)s',
                        level=(logging.DEBUG if is_debug else logging.INFO), handlers=handlers)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)

    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger("web3").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("requests").setLevel(logging.INFO)

