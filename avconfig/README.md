# AV Config Manager

A web-based utility for managing YAML configuration files with an intuitive interface for selecting and merging configuration parameters.

## Features

- Scan and visualize YAML files in a directory tree
- Select multiple YAML configurations for merging
- Duplicate detection and conflict prevention
- Safe merging into master configuration file
- Web-based interface for easy management

## Requirements

- Python 3.8+
- pip (Python package manager)

## Installation

1. Clone or download this repository
2. Navigate to the project directory:
   ```bash
   cd avconfig
   ```

3. Install required Python packages:
   ```bash
   pip install flask pyyaml
   ```

## Configuration

1. Set your root directory path in the application
2. Ensure the master config directory exists:
   ```bash
   mkdir -p ~/.config/av_core
   ```

3. Create or verify your master YAML file exists:
   ```bash
   touch ~/.config/av_core/av_param.yaml
   ```

## Running the Application

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Configure your root directory path in the web interface

4. Browse and select YAML files from the `${root}/params/nodes` directory

5. Review selections and merge into your master configuration

## Usage

1. **Set Root Directory**: Enter the path to your configuration root directory
2. **Browse Files**: Navigate the file tree to find desired YAML configurations
3. **Select Files**: Check the boxes next to YAML files you want to merge
4. **Review**: Preview selected content before merging
5. **Merge**: Safely append selected configurations to your master file

## File Structure

```
avconfig/
├── app.py              # Main Flask application
├── static/             # CSS and JavaScript files
├── templates/          # HTML templates
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Troubleshooting

- Ensure Python 3.8+ is installed: `python --version`
- Verify Flask is installed: `pip show flask`
- Check file permissions for the master config directory
- Ensure YAML files are properly formatted

## Development

To run in development mode with auto-reload:
```bash
export FLASK_ENV=development
python app.py
```

## Security Notes

- The application runs locally on your machine
- No external network access required
- Configuration files remain on your local filesystem
