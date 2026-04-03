# BinanceConnectionAPI

A few years back I was part of a project where we were using Binance, and I was tasked with getting the API to work, to be able to send trade requests to their servers. What help I found online was abysmal, so I'll share my work here so others can get better help.

The project started on Python, and I was asked to make basically every type of function to buy. Short Buy/Sell, Long Buy/Sell. There is a function that was made to easyly work with a discord bot. All functions were tested and work.

Later the project was moved to C#. The python functions were translated into C#, and some fixes were needed. *(in short there was a point where the C# wanted to order things before sanding them, but functionally they are the same).*
