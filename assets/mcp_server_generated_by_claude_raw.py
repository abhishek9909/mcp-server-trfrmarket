import os
import time
import pandas as pd
import rpy2.robjects as robjects
from rpy2.robjects.packages import importr
from mcp.server.fastmcp import FastMCP, Context
import traceback

# Set R environment variables
os.environ['R_HOME'] = r"C:\Program Files\R\R-4.5.0"
os.environ['R_USER'] = r"C:\Program Files\R\R-4.5.0"
os.environ['R_LIBS_USER'] = ""

# Create MCP server
mcp = FastMCP("WorldFootballR")

# Initialize R and install required packages
def initialize_r():
    try:
        # Check if devtools is installed
        robjects.r('''
        if (!requireNamespace("devtools", quietly = TRUE)) {
            install.packages("devtools")
        }
        ''')
        
        # Install worldfootballR package
        robjects.r('devtools::install_github("JaseZiv/worldfootballR")')
        
        # Load the package
        robjects.r('library(worldfootballR)')
        return True
    except Exception as e:
        print(f"Error initializing R: {str(e)}")
        return False

# Helper function to handle R function execution and results
def execute_r_function(r_code):
    # Sleep to avoid rate limiting
    time.sleep(6)
    
    try:
        # Load the worldfootballR package
        robjects.r('library(worldfootballR)')
        
        # Execute the R code
        result = robjects.r(r_code)
        
        # Check if the result is a data frame or similar grid-like object
        if hasattr(result, 'nrow') and callable(result.nrow):
            # It's a grid-like object, save to CSV
            temp_file = f"r_result_{time.time()}.csv"
            robjects.r(f'write.csv({r_code}, file = "{temp_file}", row.names = FALSE)')
            df = pd.read_csv(temp_file)
            return {
                "type": "dataframe",
                "file": temp_file,
                "head": str(df.head()),
                "shape": str(df.shape)
            }
        else:
            # It's a vector or list-like object
            result_list = list(result)
            file_path = f"r_result_{time.time()}.txt"
            with open(file_path, "w") as f:
                for item in result_list:
                    f.write(str(item) + "\n")
            return {
                "type": "list",
                "file": file_path,
                "glimpse": str(result_list[:5] if len(result_list) > 5 else result_list)
            }
    except Exception as e:
        return {
            "type": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }

# Initialize R when the server starts
initialize_r()

# Tool to get team URLs
@mcp.tool()
def get_team_urls(country_name: str, start_year: int) -> str:
    """
    Get team URLs for a specific country and season from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain", "Germany")
        start_year: The starting year of the season (e.g., 2020 for the 2020-2021 season)
    
    Returns:
        A list of team URLs
    """
    r_code = f'''
    team_urls <- tm_league_team_urls(
        country_name = "{country_name}",
        start_year = {start_year}
    )
    team_urls
    '''
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player URLs for a team
@mcp.tool()
def get_team_player_urls(team_url: str) -> str:
    """
    Get player URLs for a specific team from Transfermarkt.
    
    Args:
        team_url: The URL of the team's page on Transfermarkt
    
    Returns:
        A list of player URLs
    """
    r_code = f'''
    player_urls <- tm_team_player_urls(
        team_url = "{team_url}"
    )
    player_urls
    '''
    result = execute_r_function(r_code)
    return str(result)

# Tool to get staff URLs for a team
@mcp.tool()
def get_team_staff_urls(team_urls: str, staff_role: str) -> str:
    """
    Get staff URLs for specific teams and staff role from Transfermarkt.
    
    Args:
        team_urls: A single team URL or a list of team URLs (comma-separated)
        staff_role: The staff role to search for ("Manager", "Assistant Manager", "Goalkeeping Coach", "Fitness Coach", "Conditioning Coach")
    
    Returns:
        A list of staff URLs
    """
    # Handle comma-separated URLs
    if "," in team_urls:
        team_urls_list = [url.strip() for url in team_urls.split(",")]
        r_team_urls = 'c("' + '", "'.join(team_urls_list) + '")'
    else:
        r_team_urls = f'"{team_urls}"'
    
    r_code = f'''
    staff_urls <- tm_team_staff_urls(
        team_urls = {r_team_urls},
        staff_role = "{staff_role}"
    )
    staff_urls
    '''
    result = execute_r_function(r_code)
    return str(result)

# Tool to get league table by matchday
@mcp.tool()
def get_matchday_table(country_name: str, start_year: int, matchday: str, league_url: str = "") -> str:
    """
    Get league table for specific matchday(s) from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain")
        start_year: The starting year of the season (e.g., 2020 for the 2020-2021 season)
        matchday: Matchday numbers (single number or range like "1:5")
        league_url: Optional URL for leagues not in the standard dataset
    
    Returns:
        League table data
    """
    # Process matchday parameter 
    if ":" in matchday:
        start, end = matchday.split(":")
        matchday_param = f"c({start}:{end})"
    else:
        matchday_param = matchday
    
    # Construct the R code based on whether league_url is provided
    if league_url:
        r_code = f'''
        table_data <- tm_matchday_table(
            start_year = {start_year},
            matchday = {matchday_param},
            league_url = "{league_url}"
        )
        table_data
        '''
    else:
        r_code = f'''
        table_data <- tm_matchday_table(
            country_name = "{country_name}",
            start_year = {start_year},
            matchday = {matchday_param}
        )
        table_data
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get league debutants
@mcp.tool()
def get_league_debutants(country_name: str, debut_type: str, debut_start_year: int, debut_end_year: int, league_url: str = "") -> str:
    """
    Get league debutants from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain")
        debut_type: Type of debut ("league" or "pro")
        debut_start_year: The starting year of the debut season
        debut_end_year: The ending year of the debut season
        league_url: Optional URL for leagues not in the standard dataset
    
    Returns:
        League debutants data
    """
    if league_url:
        r_code = f'''
        debutants <- tm_league_debutants(
            country_name = "{country_name}",
            league_url = "{league_url}",
            debut_type = "{debut_type}",
            debut_start_year = {debut_start_year},
            debut_end_year = {debut_end_year}
        )
        debutants
        '''
    else:
        r_code = f'''
        debutants <- tm_league_debutants(
            country_name = "{country_name}",
            debut_type = "{debut_type}",
            debut_start_year = {debut_start_year},
            debut_end_year = {debut_end_year}
        )
        debutants
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get expiring contracts
@mcp.tool()
def get_expiring_contracts(country_name: str, contract_end_year: int, league_url: str = "") -> str:
    """
    Get players with expiring contracts from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain")
        contract_end_year: The year the contracts will expire
        league_url: Optional URL for leagues not in the standard dataset
    
    Returns:
        Data on players with expiring contracts
    """
    if league_url:
        r_code = f'''
        expiring <- tm_expiring_contracts(
            country_name = "{country_name}",
            contract_end_year = {contract_end_year},
            league_url = "{league_url}"
        )
        expiring
        '''
    else:
        r_code = f'''
        expiring <- tm_expiring_contracts(
            country_name = "{country_name}",
            contract_end_year = {contract_end_year}
        )
        expiring
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get league injuries
@mcp.tool()
def get_league_injuries(country_name: str, league_url: str = "") -> str:
    """
    Get current injuries in a league from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain")
        league_url: Optional URL for leagues not in the standard dataset
    
    Returns:
        Data on current injuries in the league
    """
    if league_url:
        r_code = f'''
        injuries <- tm_league_injuries(
            country_name = "{country_name}",
            league_url = "{league_url}"
        )
        injuries
        '''
    else:
        r_code = f'''
        injuries <- tm_league_injuries(
            country_name = "{country_name}"
        )
        injuries
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get team transfers
@mcp.tool()
def get_team_transfers(team_url: str, transfer_window: str = "all") -> str:
    """
    Get transfer activity for a team from Transfermarkt.
    
    Args:
        team_url: The URL of the team's page on Transfermarkt
        transfer_window: Transfer window to get data for ("summer", "winter", or "all")
    
    Returns:
        Team transfer data
    """
    r_code = f'''
    transfers <- tm_team_transfers(
        team_url = "{team_url}",
        transfer_window = "{transfer_window}"
    )
    transfers
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get squad stats
@mcp.tool()
def get_squad_stats(team_url: str) -> str:
    """
    Get squad player statistics from Transfermarkt.
    
    Args:
        team_url: The URL of the team's page on Transfermarkt
    
    Returns:
        Squad player statistics
    """
    r_code = f'''
    stats <- tm_squad_stats(
        team_url = "{team_url}"
    )
    stats
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player market values
@mcp.tool()
def get_player_market_values(country_name: str, start_year: int, league_url: str = "") -> str:
    """
    Get player market values for a league from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain")
        start_year: The starting year of the season
        league_url: Optional URL for leagues not in the standard dataset
    
    Returns:
        Player market value data
    """
    if league_url:
        r_code = f'''
        values <- tm_player_market_values(
            country_name = "{country_name}",
            start_year = {start_year},
            league_url = "{league_url}"
        )
        values
        '''
    else:
        r_code = f'''
        values <- tm_player_market_values(
            country_name = "{country_name}",
            start_year = {start_year}
        )
        values
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player bio
@mcp.tool()
def get_player_bio(player_url: str) -> str:
    """
    Get player biographical information from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
    
    Returns:
        Player biographical data
    """
    r_code = f'''
    bio <- tm_player_bio(
        player_url = "{player_url}"
    )
    bio
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player injury history
@mcp.tool()
def get_player_injury_history(player_url: str) -> str:
    """
    Get player injury history from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
    
    Returns:
        Player injury history data
    """
    r_code = f'''
    injuries <- tm_player_injury_history(
        player_urls = "{player_url}"
    )
    injuries
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player transfer history
@mcp.tool()
def get_player_transfer_history(player_url: str, get_extra_info: bool = True) -> str:
    """
    Get player transfer history from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
        get_extra_info: Whether to get extra information about transfers
    
    Returns:
        Player transfer history data
    """
    r_code = f'''
    transfers <- tm_player_transfer_history(
        player_urls = "{player_url}",
        get_extra_info = {"TRUE" if get_extra_info else "FALSE"}
    )
    transfers
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player absence
@mcp.tool()
def get_player_absence(player_url: str) -> str:
    """
    Get player absence history from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
    
    Returns:
        Player absence data
    """
    r_code = f'''
    absence <- tm_get_player_absence(
        player_urls = "{player_url}"
    )
    absence
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get team staff history
@mcp.tool()
def get_team_staff_history(team_url: str, staff_role: str) -> str:
    """
    Get history of staff members by role for a team from Transfermarkt.
    
    Args:
        team_url: The URL of the team's page on Transfermarkt
        staff_role: The staff role to search for
    
    Returns:
        Staff history data
    """
    r_code = f'''
    staff_history <- tm_team_staff_history(
        team_urls = "{team_url}",
        staff_role = "{staff_role}"
    )
    staff_history
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get staff job history
@mcp.tool()
def get_staff_job_history(staff_url: str) -> str:
    """
    Get job history for a staff member from Transfermarkt.
    
    Args:
        staff_url: The URL of the staff member's page on Transfermarkt
    
    Returns:
        Staff job history data
    """
    r_code = f'''
    job_history <- tm_staff_job_history(
        staff_urls = "{staff_url}"
    )
    job_history
    '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get player suspensions
@mcp.tool()
def get_suspensions(country_name: str = "", league_url: str = "") -> str:
    """
    Get player suspensions in a league from Transfermarkt.
    
    Args:
        country_name: The name of the country
        league_url: Optional URL for the league
    
    Returns:
        Player suspension data
    """
    if league_url:
        r_code = f'''
        suspensions <- tm_get_suspensions(
            league_url = "{league_url}"
        )
        suspensions
        '''
    else:
        r_code = f'''
        suspensions <- tm_get_suspensions(
            country_name = "{country_name}"
        )
        suspensions
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool to get players at risk of suspension
@mcp.tool()
def get_risk_of_suspension(country_name: str = "", league_url: str = "") -> str:
    """
    Get players at risk of suspension in a league from Transfermarkt.
    
    Args:
        country_name: The name of the country
        league_url: Optional URL for the league
    
    Returns:
        Data on players at risk of suspension
    """
    if league_url:
        r_code = f'''
        risk <- tm_get_risk_of_suspension(
            league_url = "{league_url}"
        )
        risk
        '''
    else:
        r_code = f'''
        risk <- tm_get_risk_of_suspension(
            country_name = "{country_name}"
        )
        risk
        '''
    
    result = execute_r_function(r_code)
    return str(result)

# Tool for running custom R code
@mcp.tool()
def run_custom_r_code(r_code: str) -> str:
    """
    Run custom R code using the worldfootballR package.
    
    Args:
        r_code: The R code to execute
    
    Returns:
        Result of the R code execution
    """
    result = execute_r_function(r_code)
    return str(result)

# Tool for executing Python code to manipulate stored data
@mcp.tool()
def execute_python_code(python_code: str) -> str:
    """
    Execute Python code to manipulate dataframes and lists stored on the computer.
    
    Args:
        python_code: The Python code to execute
    
    Returns:
        Result of the Python code execution
    """
    try:
        # Create a local namespace with common imports
        local_namespace = {
            'pd': pd,
            'os': os,
            'time': time,
            'robjects': robjects,
        }
        
        # Execute the code
        exec(python_code, {}, local_namespace)
        
        # Check if the code defines a 'result' variable
        if 'result' in local_namespace:
            return str(local_namespace['result'])
        else:
            # Look for dataframes in the local namespace
            dataframes = {name: obj for name, obj in local_namespace.items() 
                         if isinstance(obj, pd.DataFrame) and name not in ['pd']}
            
            if dataframes:
                results = {}
                for name, df in dataframes.items():
                    results[name] = {
                        "shape": df.shape,
                        "head": str(df.head())
                    }
                return str(results)
            else:
                return "Code executed successfully, but no explicit result was returned."
    except Exception as e:
        return f"Error executing Python code: {str(e)}\n{traceback.format_exc()}"

# Run the server
if __name__ == "__main__":
    mcp.run()
