# HttpAntServer
The software enables sending speed data from Training Peaks Virtual to a speed sensor using ANT+ communication. This is useful for dual recording when you want to register speed data from Training Peaks Virtual on an additional device.

## Repository Structure

The repository contains the following directories and files:

- `/src` - source code of the project
- `/docs` - project documentation
- `README.md` - basic project information
- `requirements.txt` - list of dependencies

## Installation

To run the project locally, follow these steps:

```bash
# Install Python 3.8+ with pip
sudo apt update
sudo apt install python3 python3-pip

# Install the required library
pip install openant

# Clone the repository
git clone https://github.com/user/project_name.git
cd project_name

# Generate a certificate using OpenSSL
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Add the certificate to trusted certificates on the client device (Training Peaks Virtual)
# Follow the specific device instructions to import the certificate

# Run the software with appropriate parameters (see --help for details)
python main.py --help
```

## Configuration

The program requires specific configurations:

- The Training Peaks Virtual software should be set up to broadcast client data to the server.

## Running the Software

On Ubuntu, special permissions are required for ANT stick access. Run the following command:

```bash
sudo chmod 777 /dev/bus/usb/$(lsusb | grep -i "dynastream" | awk '{print $2}')/$(lsusb | grep -i "dynastream" | awk '{print $4}' | tr -d ':')
```

Then, start the program with necessary parameters.

## Contribution

We welcome bug reports and pull requests! Please follow these guidelines:

- Fork the repository
- Work on a separate branch
- Describe changes in the pull request

## License

The project is available under the Apache License.

## Authors

- [Name] - main author
- [Other contributors]

Feel free to contribute and test the project!

