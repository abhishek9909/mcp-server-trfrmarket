import os
import time
import pandas as pd
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv
import traceback
import concurrent.futures

# Create MCP server
mcp = FastMCP("WorldFootballR")
load_dotenv()

import rpy2.robjects as robjects
from rpy2.robjects.packages import importr
from rpy2.robjects import default_converter
from rpy2.robjects.conversion import localconverter

# Initialize R and install required packages
def initialize_r():
    # Set R environment variables
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

def _run_r_code(r_code, var_name=None):
    time.sleep(6)
    
    # Load the worldfootballR package
    with localconverter(default_converter):
        robjects.r('library(worldfootballR)')

        # Execute the R code
        robjects.r(r_code)
        
        # If variable name is provided, use it to reference the result
        r_variable = var_name if var_name else "result"
        
        # Check if the variable exists in R environment
        exists_check = robjects.r(f'exists("{r_variable}")')
        if not exists_check[0]:
            return {
                "type": "error",
                "message": f"Variable '{r_variable}' not found in R environment"
            }
        
        # Get the result from R environment
        result = robjects.r(r_variable)

        if hasattr(result, 'nrow'):
            temp_file = f"r_result_{time.time()}.csv"
            robjects.r(f'write.csv({r_variable}, file = "{temp_file}", row.names = FALSE)')
            
            # Use dplyr's glimpse instead of df.head()
            robjects.r('library(dplyr)')
            robjects.r('library(utils)')
            glimpse_output = robjects.r(f'paste(capture.output(glimpse({r_variable})), collapse = "\\n")')
            columns = robjects.r(f'names({r_variable})')
            col_list = list(columns)
            
            return {
                "type": "dataframe",
                "file": temp_file,
                "glimpse": str(glimpse_output[0]),
                "shape": str(robjects.r(f'dim({r_variable})')),
                "columns": col_list
            }
        else:
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

def execute_r_function(r_code, var_name=None):
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_r_code, r_code, var_name)
            return future.result(timeout=180)  # Timeout in seconds (3 minutes)
    except concurrent.futures.TimeoutError:
        return {
            "type": "error",
            "message": "Execution time exceeded 3 minutes. The process took too long and was terminated."
        }
    except Exception as e:
        return {
            "type": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }

# Tool to get team URLs
@mcp.tool()
def get_team_urls(country_name: str, start_year: int) -> str:
    """
    Get team URLs for a specific country and season from Transfermarkt.
    
    Args:
        country_name: The name of the country (e.g., "England", "Spain", "Germany")
        start_year: The starting year of the season (e.g., 2020 for the 2020-2021 season)
    
    Returns:
        type: list | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: str | None # Glimpse of the data (the first 5 urls).
    """
    r_code = f'''
    team_urls <- tm_league_team_urls(
        country_name = "{country_name}",
        start_year = {start_year}
    )
    '''
    result = execute_r_function(r_code, "team_urls")
    return str(result)

# Tool to get player URLs for a team
@mcp.tool()
def get_team_player_urls(team_url: str) -> str:
    """
    Get player URLs for a specific team from Transfermarkt.
    
    Args:
        team_url: The URL of the team's page on Transfermarkt
    
    Returns:
        type: list | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: str | None # Glimpse of the data (the first 5 urls).
    """
    r_code = f'''
    player_urls <- tm_team_player_urls(
        team_url = "{team_url}"
    )
    '''
    result = execute_r_function(r_code, "player_urls")
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
        type: list | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: str | None # Glimpse of the data (the first 5 urls).
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
    '''
    result = execute_r_function(r_code, "staff_urls")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names. (Expected column names: \'country\', \'league\', \'matchday\', \'rk\', \'squad\', \'p\', \'w\', \'d\', \'l\', \'gf\', \'ga\', \'g_diff\', \'pts\')
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
        '''
    else:
        r_code = f'''
        table_data <- tm_matchday_table(
            country_name = "{country_name}",
            start_year = {start_year},
            matchday = {matchday_param}
        )
        '''
    
    result = execute_r_function(r_code, "table_data")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names Expected column names: \'comp_name\', \'country\', \'comp_url\', \'player_name\', \'player_url\', \'position\', \'nationality\', \'second_nationality\', \'debut_for\', \'debut_date\', \'opponent\', \'goals_for\', \'goals_against\', \'age_debut\', \'value_at_debut\', \'player_market_value\', \'appearances\', \'goals\', \'minutes_played\', \'debut_type\'
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
        '''
    else:
        r_code = f'''
        debutants <- tm_league_debutants(
            country_name = "{country_name}",
            debut_type = "{debut_type}",
            debut_start_year = {debut_start_year},
            debut_end_year = {debut_end_year}
        )
        '''
    
    result = execute_r_function(r_code, "debutants")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names Expected column names: \'comp_name\', \'country\', \'comp_url\', \'player_name\', \'player_url\', \'date_of_birth\', \'position\', \'nationality\', \'second_nationality\', \'current_club\', \'contract_expiry\', \'contract_option\', \'player_market_value\', \'transfer_fee\', \'agent\'
    """
    if league_url:
        r_code = f'''
        expiring <- tm_expiring_contracts(
            country_name = "{country_name}",
            contract_end_year = {contract_end_year},
            league_url = "{league_url}"
        )
        '''
    else:
        r_code = f'''
        expiring <- tm_expiring_contracts(
            country_name = "{country_name}",
            contract_end_year = {contract_end_year}
        )
        '''
    
    result = execute_r_function(r_code, "expiring")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'comp_name\', \'country\', \'comp_url\', \'player_name\', \'player_url\', \'position\', \'current_club\', \'age\', \'nationality\', \'second_nationality\', \'injury\', \'injured_since\', \'injured_until\', \'player_market_value\'
    """
    if league_url:
        r_code = f'''
        injuries <- tm_league_injuries(
            country_name = "{country_name}",
            league_url = "{league_url}"
        )
        '''
    else:
        r_code = f'''
        injuries <- tm_league_injuries(
            country_name = "{country_name}"
        )
        '''
    
    result = execute_r_function(r_code, "injuries")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'team_name\', \'league\', \'country\', \'season\', \'transfer_type\', \'player_name\', \'player_url\', \'player_position\', \'player_age\', \'player_nationality\', \'club_2\', \'league_2\', \'country_2\', \'transfer_fee\', \'is_loan\', \'transfer_notes\', \'window\', \'in_squad\', \'appearances\', \'goals\', \'minutes_played\'
    """
    r_code = f'''
    transfers <- tm_team_transfers(
        team_url = "{team_url}",
        transfer_window = "{transfer_window}"
    )
    '''
    
    result = execute_r_function(r_code, "transfers")
    return str(result)

# Tool to get squad stats
@mcp.tool()
def get_squad_stats(team_url: str) -> str:
    """
    Get squad player statistics from Transfermarkt.
    
    Args:
        team_url: The URL of the team's page on Transfermarkt
    
    Returns:
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'team_name\', \'league\', \'country\', \'player_name\', \'player_url\', \'player_pos\', \'player_age\', \'nationality\', \'in_squad\', \'appearances\', \'goals\', \'minutes_played\'
    """
    r_code = f'''
    stats <- tm_squad_stats(
        team_url = "{team_url}"
    )
    '''
    
    result = execute_r_function(r_code, "stats")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'comp_name\', \'region\', \'country\', \'season_start_year\', \'squad\', \'player_num\', \'player_name\', \'player_position\', \'player_dob\', \'player_age\', \'player_nationality\', \'current_club\', \'player_height_mtrs\', \'player_foot\', \'date_joined\', \'joined_from\', \'contract_expiry\', \'player_market_value_euro\', \'player_url\'
    """
    if league_url:
        r_code = f'''
        values <- tm_player_market_values(
            country_name = "{country_name}",
            start_year = {start_year},
            league_url = "{league_url}"
        )
        '''
    else:
        r_code = f'''
        values <- tm_player_market_values(
            country_name = "{country_name}",
            start_year = {start_year}
        )
        '''
    
    result = execute_r_function(r_code, "values")
    return str(result)

# Tool to get player bio
@mcp.tool()
def get_player_bio(player_url: str) -> str:
    """
    Get player biographical information from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
    
    Returns:
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'player_name\', \'player_id\', \'citizenship\', \'position\', \'current_club\', \'joined\', \'contract_expires\', \'player_valuation\', \'max_player_valuation\', \'max_player_valuation_date\', \'squad_number\', \'URL\', \'picture_url\', \'date_of_birth\'
    """
    r_code = f'''
    bio <- tm_player_bio(
        player_url = "{player_url}"
    )
    '''
    
    result = execute_r_function(r_code, "bio")
    return str(result)

# Tool to get player injury history
@mcp.tool()
def get_player_injury_history(player_url: str) -> str:
    """
    Get player injury history from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
    
    Returns:
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'player_name\', \'player_url\', \'season_injured\', \'injury\', \'injured_since\', \'injured_until\', \'duration\', \'games_missed\', \'club_missed_games_for\
    """
    r_code = f'''
    injuries <- tm_player_injury_history(
        player_urls = "{player_url}"
    )
    '''
    
    result = execute_r_function(r_code, "injuries")
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
    '''
    
    result = execute_r_function(r_code, "transfers")
    return str(result)

# Tool to get player absence
@mcp.tool()
def get_player_absence(player_url: str) -> str:
    """
    Get player absence history from Transfermarkt.
    
    Args:
        player_url: The URL of the player's page on Transfermarkt
    
    Returns:
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'player_name\', \'player_url\', \'season\', \'absence_suspension\', \'competition\', \'from\', \'until\', \'days\', \'games_missed\', \'club_missed\
    """
    r_code = f'''
    absence <- tm_get_player_absence(
        player_urls = "{player_url}"
    )
    '''
    
    result = execute_r_function(r_code, "absence")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names: \'team_name\', \'league\', \'country\', \'staff_role\', \'staff_name\', \'staff_url\', \'staff_dob\', \'staff_nationality\', \'staff_nationality_secondary\', \'appointed\', \'end_date\', \'days_in_post\', \'matches\', \'wins\', \'draws\', \'losses\', \'ppg\'
    """
    r_code = f'''
    staff_history <- tm_team_staff_history(
        team_urls = "{team_url}",
        staff_role = "{staff_role}"
    )
    '''
    
    result = execute_r_function(r_code, "staff_history")
    return str(result)

# Tool to get staff job history
@mcp.tool()
def get_staff_job_history(staff_url: str) -> str:
    """
    Get job history for a staff member from Transfermarkt.
    
    Args:
        staff_url: The URL of the staff member's page on Transfermarkt
    
    Returns:
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names:  \'name\', \'current_club\', \'current_role\', \'date_of_birth\', \'citizenship\', \'coaching_licence\', \'avg_term_as_coach\', \'position\', \'club\', \'appointed\', \'contract_expiry\', \'days_in_charge\', \'matches\', \'wins\', \'draws\', \'losses\', \'players_used\', \'avg_goals_for\', \'avg_goals_against\', \'ppm\', \'staff_url\'
    """
    r_code = f'''
    job_history <- tm_staff_job_history(
        staff_urls = "{staff_url}"
    )
    '''
    
    result = execute_r_function(r_code, "job_history")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names:  \'Country\', \'Competition\', \'Player\', \'Position\', \'Club\', \'Age\', \'Reason\', \'Since\', \'Until\', \'Matches_Missed\'
    """
    if league_url:
        r_code = f'''
        suspensions <- tm_get_suspensions(
            league_url = "{league_url}"
        )
        '''
    else:
        r_code = f'''
        suspensions <- tm_get_suspensions(
            country_name = "{country_name}"
        )
        '''
    
    result = execute_r_function(r_code, "suspensions")
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
        type: dataframe | error
        file: str | None # Path to the text file containing all the URLs.
        glimpse: Returns a glimpse showing number of rows and columns and a glimpse of the data.
        shape: str | None # Shape of the dataframe.
        columns: list | None # List of column names, Expected column names:  \'Country\', \'Competition\', \'Player\', \'Position\', \'Club\', \'Age\', \'Yellow_Cards\'
    """
    if league_url:
        r_code = f'''
        risk <- tm_get_risk_of_suspension(
            league_url = "{league_url}"
        )
        '''
    else:
        r_code = f'''
        risk <- tm_get_risk_of_suspension(
            country_name = "{country_name}"
        )
        '''
    
    result = execute_r_function(r_code, "risk")
    return str(result)

# Tool for running custom R code
# @mcp.tool()
# def run_custom_r_code(r_code: str) -> str:
#     """
#     Run custom R code using the worldfootballR package.
    
#     Args:
#         r_code: The R code to execute
    
#     Returns:
#         Result of the R code execution
#     """
#     result = execute_r_function(r_code)
#     return str(result)

# # Tool for executing Python code to manipulate stored data
@mcp.tool()
def execute_python_code(python_code: str) -> str:
    """
    Execute Python code to manipulate dataframes and lists stored on the computer.
    Write code into `intermediate_result.txt` file.
    Note:
        - For dataframes, use encoding="ISO-8859-1" when reading CSV files.
        - For lists, use `f.readlines()` to read the file content.
    
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
        
        with open(f"r_result_pythoncode_{time.time()}.py", "w") as f:
            f.write(python_code)

        # Execute the code
        exec(python_code, {}, local_namespace)
        
        # Check if the code defines a 'result' variable
        if os.path.exists("intermediate_result.txt"):
            with open("intermediate_result.txt", "r") as f:
                result = f.read()
            os.remove("intermediate_result.txt")
            return "Result of the execution: " + result
        else:
            return "Code executed successfully, but no explicit result was returned, Create a file named `intermediate_result.txt` to store the result."
    except Exception as e:
        return f"Error executing Python code: {str(e)}\n{traceback.format_exc()}"

# Run the server
if __name__ == "__main__":
    # Initialize R when the server starts
    initialize_r()
    mcp.run()