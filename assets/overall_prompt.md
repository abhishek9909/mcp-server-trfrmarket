Model Context Protocol is a new concept created by Anthropic standardization communication process using LLMS.
- It is attached as file.

You are requested to create an MCP server in python. Here is how the SDK looks like
- It is attached as file.

I want to create an MCP server that uses `rpy2` to use R helper functions provided by the package: `JaseZiv/worldfootballR`
In in the initialization step, I need to do this:

```python
import time
import os
import pandas as pd
os.environ['R_HOME'] = "C:\Program Files\R\R-4.5.0"
os.environ['R_USER'] = "C:\Program Files\R\R-4.5.0"
os.environ['R_LIBS_USER'] = "C:/Users/abhmishra/Desktop/RLib/library" # Keep these paths as absolute like this for now.

from rpy2.robjects.packages import importr
import rpy2.robjects as robjects
robjects.r('''
if (!requireNamespace("devtools", quietly = TRUE)) {
    install.packages("devtools")
}
''')

# Use devtools to install the worldfootballR package from GitHub
robjects.r('devtools::install_github("JaseZiv/worldfootballR")')
```

When executing an R function like: `mapped_players <- player_dictionary_mapping()`

I use this python code:

```python
# Load the worldfootballR package in python
robjects.r('library(worldfootballR)')
# Call player_dictionary_mapping() and store the result
robjects.r('mapped_players <- player_dictionary_mapping()')

## If the result is grid, use this code like this to return result.
robjects.r('write.csv(mapped_players, file = "mapped_players.csv", row.names = FALSE)')
file_path = f"mapped_players_{time.time()}.csv"
df = pd.read_csv(file_path, index = False)
return {
    "file": file_path,
    "head": str(df.head())
}
```
## Else if the result is a string or list of strings, directly return as plaintext.

```python
robjects.r('library(worldfootballR)')

# Call the R function with country and year
robjects.r('''
team_urls <- tm_league_team_urls(
    country_name = "England",
    start_year = 2020
)
''')
# Convert to Python list
team_urls = list(robjects.r('team_urls'))
file_path = f"team_urls_{time.time()}.txt"
with open(file_path, "w") as f:
    f.writelines(team_urls)
return {
    "file": file_path,
    "glimpse": team_urls[:5]
}
```

Here are the helper functions, expose each function as a `tool` in MCP

- It is attached as file.

In addition to this
- make sure to add 6 seconds of sleep before executing any R function to avoid unneccessary rate limiting errors.
- create another tool that is used for performing operations on dataframes and lists stored in computer.
  - the only argument provided is the python code.
  - the mcp server uses `exec()` commands to run the code.