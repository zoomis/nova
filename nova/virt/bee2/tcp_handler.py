#Copyright (C) 2012, The SAVI Project.

__author__ = 'Bo Bao (bob.bao@mail.utoronto.ca)'
__author__ = 'Hesam, Rahimi Koopayi (hesam.rahimikoopayi@utoronto.ca)'

import socket
import os
#from libs.customized_logging import logger

def tcp_handler (cmd, fpga_num, subagent_address, dir_path=0):
    result = "OK"
    # open a socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #client_socket.connect(("", 6677))
    subagent_address_components = subagent_address.split(":")
    subagent_ip_address = subagent_address_components[0]
    subagent_port = subagent_address_components[1]
    client_socket.connect((subagent_ip_address, int(subagent_port)))
    client_socket.settimeout(10)

    #send request
    try:
        print("TCP SEND COMMAND:"+cmd)
        print("TCP SEND FPGA_NUM:" +str(fpga_num))
        client_socket.send(cmd + "\r\n")
        client_socket.send(str(fpga_num) + "\r\n")
        if (cmd == "PRG"):
            size = str(os.path.getsize(dir_path))
            print ("FPGA-IMAGE size is=%s", size) 
            client_socket.send(str(size) + "\r\n")
        client_socket.send("\r\n")
        if (cmd == "PRG"):
            bit_file = open(dir_path)
            data = bit_file.read(1024)
            while (data != ""):
                client_socket.send(data)
                data = bit_file.read(1024)

    except socket.timeout:
        result = -1
        message = "socket timeout"

    #wait for response
    if (result == "OK"):
        try:
            response = client_socket.recv(512)
            print("The response is :" + response)
            if (response == ""):
                result = -1
                message = "not receive response before closing connection"
            else:
                response_array = response.split("\r\n")
                if (len(response_array) != 4):
                    result = -1
                    message = "response message is too long or in incorrect format"
                else:
                    result = response_array[0]
                    message = response_array[1]
                    print("The third part"+response_array[2])
                    print("The fourth part"+response_array[3])
                    if (not (response_array[2] == "" and response_array[3] == "")):
                        result = -1
                        message = "response message format not correct"
        except socket.timeout:
            result = -1
            message = "socket timeout"

    print("Result is:" + str(result))
    print("Message is :" + message)
    return result, message

