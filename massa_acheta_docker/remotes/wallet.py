from loguru import logger

import json
from aiogram.utils.formatting import as_list, as_line, Code, TextLink

from app_config import app_config
import app_globals

from telegram.queue import queue_telegram_message
from tools import pull_http_api, get_short_address, t_now


@logger.catch
async def check_wallet(node_name: str = "", wallet_address: str = "") -> None:
    logger.debug(f"-> Enter Def")

    if app_globals.app_results[node_name]['last_status'] != True:
        logger.warning(
            f"Will not watch wallet '{wallet_address}'@'{node_name}' because of its offline")

        app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] = False
        app_globals.app_results[node_name]['wallets'][wallet_address]['last_result'] = {
            "error": "Host node is offline"}

        return

    payload = json.dumps(
        {
            "id": 0,
            "jsonrpc": "2.0",
            "method": "get_addresses",
            "params": [[wallet_address]]
        }
    )

    wallet_answer = {"error": "No response from remote HTTP API"}
    try:
        wallet_answer = await pull_http_api(api_url=app_globals.app_results[node_name]['url'],
                                            api_method="POST",
                                            api_payload=payload,
                                            api_root_element="result")

        wallet_result = wallet_answer.get("result", None)
        if not wallet_result:
            raise Exception(
                f"Wrong answer from MASSA node API ({str(wallet_answer)})")

        if type(wallet_result) != list or not len(wallet_result):
            raise Exception(
                f"Wrong answer from MASSA node API ({str(wallet_answer)})")

        wallet_result = wallet_result[0]
        wallet_result_address = wallet_result.get("address", None)

        if wallet_result_address != wallet_address:
            raise Exception(
                f"Bad address received from MASSA node API: '{wallet_result_address}' (expected '{wallet_address}')")

        wallet_final_balance = 0
        wallet_final_balance = wallet_result.get("final_balance", 0)
        wallet_final_balance = float(wallet_final_balance)
        wallet_final_balance = round(wallet_final_balance, 4)

        wallet_candidate_rolls = 0
        wallet_candidate_rolls = wallet_result.get("candidate_roll_count", 0)
        wallet_candidate_rolls = int(wallet_candidate_rolls)

        wallet_cycle_infos = wallet_result.get("cycle_infos", None)
        if not wallet_cycle_infos or type(wallet_cycle_infos) != list or len(wallet_cycle_infos) == 0:
            raise Exception(f"Bad cycle_infos for wallet '{wallet_address}'")

        wallet_active_rolls = 0
        if type(wallet_cycle_infos[-1].get("active_rolls", 0)) == int:
            wallet_active_rolls = wallet_cycle_infos[-1].get("active_rolls", 0)

        wallet_operated_blocks = 0
        for cycle_info in wallet_cycle_infos:
            if type(cycle_info.get("ok_count", 0)) == int:
                wallet_operated_blocks += cycle_info.get("ok_count", 0)

        wallet_missed_blocks = 0
        for cycle_info in wallet_cycle_infos:
            if type(cycle_info.get("nok_count", 0)) == int:
                wallet_missed_blocks += cycle_info.get("nok_count", 0)

    except BaseException as E:
        logger.warning(
            f"Error watching wallet '{wallet_address}' on '{node_name}': ({str(E)})")

        if app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] != False:
            t = as_list(
                f"🏠 Node: \"{node_name}\"",
                as_line(f"📍 {app_globals.app_results[node_name]['url']}"),
                as_line(
                    "🚨 Cannot get info for wallet: ",
                    TextLink(
                        await get_short_address(address=wallet_address),
                        url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                    )
                ),
                as_line(
                    "💥 Exception: ",
                    Code(str(E))
                ),
                "⚠ Check wallet address or node settings!"
            )
            await queue_telegram_message(message_text=t.as_html())

        app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] = False
        app_globals.app_results[node_name]['wallets'][wallet_address]['last_result'] = wallet_answer

    else:
        logger.info(
            f"Got wallet '{wallet_address}'@'{node_name}' info successfully!")

        if app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] != True:
            t = as_list(
                f"🏠 Node: \"{node_name}\"",
                as_line(f"📍 {app_globals.app_results[node_name]['url']}"),
                as_line(
                    "👛 Successfully got info for wallet: ",
                    TextLink(
                        await get_short_address(address=wallet_address),
                        url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                    )
                ),
                f"💰 Final balance: {wallet_final_balance:,} MAS",
                f"🗞 Candidate / Active rolls: {wallet_candidate_rolls:,} / {wallet_active_rolls:,}",
                f"🥊 Missed blocks: {wallet_missed_blocks}"
            )
            await queue_telegram_message(message_text=t.as_html())

        else:
            # 1) Check if balance is decreased:
            if wallet_final_balance < app_globals.app_results[node_name]['wallets'][wallet_address]['final_balance']:
                t = as_list(
                    f"🏠 Node: \"{node_name}\"",
                    as_line(f"📍 {app_globals.app_results[node_name]['url']}"),
                    as_line(
                        "💸 Decreased balance on wallet: ",
                        TextLink(
                            await get_short_address(address=wallet_address),
                            url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                        )
                    ),
                    f"👁 New final balance: {app_globals.app_results[node_name]['wallets'][wallet_address]['final_balance']:,} → {wallet_final_balance:,} MAS",
                )
                await queue_telegram_message(message_text=t.as_html())

            # 2) Check if candidate rolls changed:
            if wallet_candidate_rolls != app_globals.app_results[node_name]['wallets'][wallet_address]['candidate_rolls']:
                t = as_list(
                    f"🏠 Node: \"{node_name}\"",
                    as_line(f"📍 {app_globals.app_results[node_name]['url']}"),
                    as_line(
                        "🗞 Candidate rolls changed on wallet: ",
                        TextLink(
                            await get_short_address(address=wallet_address),
                            url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                        )
                    ),
                    f"👁 New candidate rolls number: {app_globals.app_results[node_name]['wallets'][wallet_address]['candidate_rolls']:,} → {wallet_candidate_rolls:,}"
                )
                await queue_telegram_message(message_text=t.as_html())

            # 3) Check if active rolls changed:
            if wallet_active_rolls != app_globals.app_results[node_name]['wallets'][wallet_address]['active_rolls']:
                t = as_list(
                    f"🏠 Node: \"{node_name}\"",
                    as_line(f"📍 {app_globals.app_results[node_name]['url']}"),
                    as_line(
                        "🗞 Active rolls changed on wallet: ",
                        TextLink(
                            await get_short_address(address=wallet_address),
                            url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                        )
                    ),
                    f"👁 New active rolls number: {app_globals.app_results[node_name]['wallets'][wallet_address]['active_rolls']:,} → {wallet_active_rolls:,}"
                )
                await queue_telegram_message(message_text=t.as_html())

            # Compare with last stored cycle stats
            last_cycle = app_globals.app_results[node_name]['wallets'][wallet_address]['last_cycle']
            last_ok = app_globals.app_results[node_name]['wallets'][wallet_address]['last_ok_count']
            last_nok = app_globals.app_results[node_name]['wallets'][wallet_address]['last_nok_count']

            current_cycle = wallet_cycle_infos[-1].get("cycle", 0)
            ok_count = wallet_cycle_infos[-1].get("ok_count", 0)
            nok_count = wallet_cycle_infos[-1].get("nok_count", 0)

            if current_cycle != last_cycle:
                new_ok = ok_count
                new_nok = nok_count
            else:
                new_ok = ok_count - last_ok
                new_nok = nok_count - last_nok

            if new_ok > 0:
                # Try to get block identifiers for the newly produced blocks
                block_ids: list[str] = []
                try:
                    payload_blocks = json.dumps(
                        {
                            "id": 0,
                            "jsonrpc": "2.0",
                            "method": "get_blocks",
                            "params": [
                                {
                                    "creator": wallet_address,
                                    "limit": new_ok
                                }
                            ]
                        }
                    )

                    blocks_answer = await pull_http_api(
                        api_url=app_globals.app_results[node_name]['url'],
                        api_method="POST",
                        api_payload=payload_blocks,
                        api_root_element="result"
                    )

                    blocks_result = blocks_answer.get("result", None)
                    if blocks_result and isinstance(blocks_result, list):
                        for block in blocks_result:
                            block_id = block.get("id", None)
                            if block_id:
                                block_ids.append(block_id)
                except BaseException as E:
                    logger.warning(
                        f"Cannot get produced block ids for '{wallet_address}'@'{node_name}': ({str(E)})")

                for idx in range(new_ok):
                    block_id = block_ids[idx] if idx < len(block_ids) else ""

                    if block_id:
                        block_link = TextLink(
                            block_id,
                            url=f"{app_config['service']['mainnet_explorer_url']}/block/{block_id}"
                        )
                        line = as_line(
                            "✅ Nouveau bloc ",
                            block_link,
                            " produit par : ",
                            TextLink(
                                await get_short_address(address=wallet_address),
                                url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                            )
                        )
                    else:
                        line = as_line(
                            "✅ Nouveau bloc produit par : ",
                            TextLink(
                                await get_short_address(address=wallet_address),
                                url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                            )
                        )

                    t = as_list(
                        f"🏠 Node: \"{node_name}\"",
                        as_line(
                            f"📍 {app_globals.app_results[node_name]['url']}"),
                        line
                    )
                    await queue_telegram_message(message_text=t.as_html())

            if new_nok > 0:
                t = as_list(
                    f"🏠 Node: \"{node_name}\"",
                    as_line(f"📍 {app_globals.app_results[node_name]['url']}"),
                    as_line(
                        "🥊 New missed blocks on wallet: ",
                        TextLink(
                            await get_short_address(address=wallet_address),
                            url=f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                        )
                    ),
                    f"👁 Blocks missed in last cycles: {wallet_missed_blocks}"
                )
                await queue_telegram_message(message_text=t.as_html())

            # Update last cycle stats for next iteration
            app_globals.app_results[node_name]['wallets'][wallet_address]['last_cycle'] = current_cycle
            app_globals.app_results[node_name]['wallets'][wallet_address]['last_ok_count'] = ok_count
            app_globals.app_results[node_name]['wallets'][wallet_address]['last_nok_count'] = nok_count

            time_now = await t_now()

        try:
            app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] = True
            app_globals.app_results[node_name]['wallets'][wallet_address]['last_update'] = time_now

            app_globals.app_results[node_name]['wallets'][wallet_address]['final_balance'] = wallet_final_balance
            app_globals.app_results[node_name]['wallets'][wallet_address]['candidate_rolls'] = wallet_candidate_rolls
            app_globals.app_results[node_name]['wallets'][wallet_address]['active_rolls'] = wallet_active_rolls
            app_globals.app_results[node_name]['wallets'][wallet_address]['missed_blocks'] = wallet_missed_blocks
            app_globals.app_results[node_name]['wallets'][wallet_address]['produced_blocks'] = wallet_operated_blocks


            app_globals.app_results[node_name]['wallets'][wallet_address]['last_result'] = wallet_result

            # Use the previous cycle stats if available,
            # otherwise fall back to the latest cycle to avoid IndexError
            if len(wallet_cycle_infos) >= 2:
                final_cycle = wallet_cycle_infos[-2]
            else:
                final_cycle = wallet_cycle_infos[-1]

            wallet_last_cycle = 0
            if type(final_cycle.get("cycle", 0)) == int:
                wallet_last_cycle = final_cycle.get("cycle", 0)

            wallet_active_rolls = 0
            if type(final_cycle.get("active_rolls", 0)) == int:
                wallet_active_rolls = final_cycle.get("active_rolls", 0)

            wallet_last_cycle_operated_blocks = 0
            if type(final_cycle.get("ok_count", 0)) == int:
                wallet_last_cycle_operated_blocks = final_cycle.get(
                    "ok_count", 0)

            wallet_last_cycle_missed_blocks = 0
            if type(final_cycle.get("nok_count", 0)) == int:
                wallet_last_cycle_missed_blocks = final_cycle.get(
                    "nok_count", 0)

            app_globals.app_results[node_name]['wallets'][wallet_address]['stat'].append(
                {
                    "time": time_now,
                    "cycle": wallet_last_cycle,
                    "balance": wallet_final_balance,
                    "rolls": wallet_active_rolls,
                    "total_rolls": app_globals.massa_network['values']['total_staked_rolls'],
                    "ok_blocks": wallet_last_cycle_operated_blocks,
                    "nok_blocks": wallet_last_cycle_missed_blocks,
                    "produced_blocks": wallet_operated_blocks,
                    "produced_blocks_cycle": wallet_last_cycle_operated_blocks,
                }
            )

        except BaseException as E:
            logger.warning(
                f"Cannot store stat for wallet '{wallet_address}'@'{node_name}' ({str(E)})")

        else:
            logger.info(
                f"Stored stat for wallet '{wallet_address}'@'{node_name}' ({len(app_globals.app_results[node_name]['wallets'][wallet_address]['stat'])} measures)")

    return


if __name__ == "__main__":
    pass
