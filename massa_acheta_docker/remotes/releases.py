from loguru import logger

from app_config import app_config
import app_globals

from alert_manager import send_alert
from remotes_utils import pull_http_api


def format_html_message(lines: list[str]) -> str:
    """Assemble une liste de lignes avec sauts de ligne HTML."""
    return "\n".join(lines)


def text_link(text: str, url: str) -> str:
    """Crée un lien HTML cliquable."""
    return f'<a href="{url}">{text}</a>'


@logger.catch
async def massa_release() -> None:
    logger.debug("-> massa_release")

    massa_release_answer = {"error": "No response from remote HTTP API"}
    try:
        massa_release_answer = await pull_http_api(
            api_url=app_config['service']['massa_release_url'],
            api_method="GET",
            api_root_element="name"
        )

        massa_release_result = massa_release_answer.get("result", None)
        if not massa_release_result:
            raise Exception(f"Wrong answer from '{app_config['service']['massa_release_url']}' ({massa_release_answer})")

    except BaseException as E:
        logger.warning(f"Cannot get latest MASSA release version: ({E}). Result: {massa_release_answer}")

    else:
        logger.info(f"Got latest MASSA release version: '{massa_release_result}' (current is: '{app_globals.massa_network['values']['latest_release']}')")

        if app_globals.massa_network['values']['latest_release'] == "":
            pass

        elif app_globals.massa_network['values']['latest_release'] != massa_release_result:
            message_lines = [
                f"💾 A new MASSA version released: <b>{massa_release_result}</b>",
                "",
                "⚠ Check your nodes and update if needed!"
            ]
            await send_alert(
                alert_type="massa_release",
                level="info",
                html=format_html_message(message_lines)
            )

        app_globals.massa_network['values']['latest_release'] = massa_release_result


@logger.catch
async def acheta_release() -> None:
    logger.debug("-> acheta_release")

    try:
        acheta_release_answer = await pull_http_api(
            api_url=app_config['service']['acheta_release_url'],
            api_method="GET",
            api_root_element="tag_name"
        )

        acheta_release_result = acheta_release_answer.get("result", None)
        if not acheta_release_result:
            raise Exception(f"Wrong answer from MASSA node API ({acheta_release_answer})")

    except BaseException as E:
        logger.warning(f"Cannot get latest ACHETA release version: ({E}). Result: {acheta_release_answer}")

    else:
        logger.info(f"Got latest ACHETA release version: '{acheta_release_result}' (local is: '{app_globals.local_acheta_release}')")

        if app_globals.latest_acheta_release == "":
            app_globals.latest_acheta_release = app_globals.local_acheta_release

        if app_globals.latest_acheta_release != acheta_release_result:
            message_lines = [
                f"🦗 A new ACHETA version released: <b>{acheta_release_result}</b>",
                "",
                f"💾 You have version: <b>{app_globals.local_acheta_release}</b>",
                "",
                f"⚠ Update your bot version – {text_link('More info here', 'https://github.com/COLOC-BOB/Massa-acheta-docker/releases')}"
            ]
            await send_alert(
                alert_type="acheta_release",
                level="info",
                html=format_html_message(message_lines) 
            )

            app_globals.latest_acheta_release = acheta_release_result


@logger.catch
async def check_releases() -> None:
    logger.debug("-> check_releases")
    await massa_release()
    await acheta_release()


if __name__ == "__main__":
    pass
