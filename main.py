import argparse
from time import sleep
from config import RESULT_FILE
from runner import Runner
import logging

from player import SimplePlayer


def main(host: str = 'localhost', port: int = 5000, log_file: bool= False, result_path=RESULT_FILE, simulation: bool = False, simulation_round: int = 6, local: bool = False) -> None:
    """Main entry point for the poker bot runner."""
    
    # Configure logger to write to a file
    if log_file:
        logging.basicConfig(
            filename='poker_runner.log',
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    if local:
        print("Running in local mode, saving results to local file")
        result_path = 'game_result.log'

    if simulation:
        print(f"Running in simulation mode for {simulation_round} rounds")
        count = 0
        total_score = 0
        while count < simulation_round:
            print(f"Running simulation round {count + 1}/{simulation_round}")
            runner = Runner(host, port, result_path, simulation)
            simple_bot = SimplePlayer()
            runner.set_bot(simple_bot)
            runner.run()
            runner.close()

            score = runner.get_score()
            total_score += score

            sleep(0.1)
            if runner.run_success:
                print(f"Simulation round {count + 1} completed successfully")
                count += 1
        print(f"Simulation completed. Total score: {total_score}")
        print(f"Average score per round: {total_score / simulation_round}")

        runner.append_to_file(result_path, str(int(total_score / simulation_round)))

    else:
        runner = Runner(host, port, result_path, simulation)
        simple_bot = SimplePlayer()
        runner.set_bot(simple_bot)
        runner.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poker Bot Runner")
    parser.add_argument('-H', '--host', type=str, default='localhost', help='Server hostname or IP address')
    parser.add_argument('-p', '--port', type=int, default=5000, help='Server port')
    parser.add_argument('-lf', '--log_file', type=bool, default=False, help='Log to file or console')
    parser.add_argument('-r', '--result', type=str, default=RESULT_FILE, help='File to save the result')
    parser.add_argument('-s', '--simulation', type=bool, default=False, help='Run in simulation mode')
    parser.add_argument('-sr', '--simulation_rounds', type=int, default=6, help='Number of rounds in simulation mode')
    parser.add_argument('-l', '--local', type=bool, default=False, help='Run in local mode')
    args = parser.parse_args()

    # Run the main function with command line arguments
    try:
        main(args.host, args.port, args.log_file, args.result, args.simulation, args.simulation_rounds, args.local)
    except KeyboardInterrupt:
        print("\nExiting...")