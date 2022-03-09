# liquidator-bot

## Installation
```bash
docker pull velerofinance/liquidator_bot:latest
```

## ENV Variables
    - AUCTIONEER_PK  # (required) The private key of the account that will participate in the auctions. This address pays for all transactions
    - IS_DEBUG  # (default=false) activate debug logs
    - RPC_URL  # (default=https://evmexplorer.velas.com/rpc) url to http json rpc
    - EXTERNAL_BLOCK_EXPLORER_URL  # (default=https://evmexplorer.velas.com/api) Link to explorer on the selected network
    - CHAIN_LOG_ADDRESS  # (default=0x87986E3AC1F67aDc36027Df78fBfc06CbB36E768) Address of the VELERO contract CHAIN_LOG
    - PERCENT_PRICE_DELTA  # (default=-7.0) Minimum percentage difference from the market price at which the bot can redeem the collateral asset
    - WAGYU_SLIPPAGE  # (default=0.5) Wagyu Slippage Tolerance
    - WAGYU_ROUTER_ADDRESS  # (default=0x3D1c58B6d4501E34DF37Cf0f664A58059a188F00) Wagyu Router Contract address
    - TG_BOT_KEY  # (default=null) The key of the telegram bot that will send notifications about the operation of the auction bot. If the value is not set, the notifications in the telegram will be disabled
    - TG_CHAT_ID  # (default=null) ID of the chat to which notifications from the bot will be sent. If the value is not set, the notifications in the telegram will be disabled

## RUN
Before launching, make a deposit USDV to your account on [liquidation.velero.finance](https://liquidation.velero.finance/?network=velas).
You can generate a USDV to participate in auctions at [vaults.velero.finance](https://vaults.velero.finance/?network=velas).
```bash
mkdir liquidator_bot_logs
docker run  --name velero_bot_liquidator -v $(pwd)/liquidator_bot_logs:/app/log -e AUCTIONEER_PK=0x0000000000000000000000000000000000000000000000000000000000000000 -e PERCENT_PRICE_DELTA=-7.0 -e TG_BOT_KEY=0000000000:AAAAAAAAAAAAAAAAAAAAAAAAA-kkkkkkkkk -e TG_CHAT_ID=000000001 velerofinance/liquidator_bot:latest
```