I would like to make a utility wiht the UI that serves from the web and backend with python. The aim will be to be able to define a root directory and within the root directory:
1. it scans the path ${root}/params/nodes and its subdirectories for yaml files
2. There is a master yaml file in ~/.config/av_core/av_param.yaml
3. av_param.yaml conains a subset of the combined contents of the subdirectory yaml files mentioend in point 1
4. I want a web interface that lets me select files from the subdirectory yaml files and append them into the av_param.yaml.
5. If the selected yaml is already contained inside av_param.yaml it should throw an alert or error.
