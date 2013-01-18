#include "stdio.h"
#include "string.h"
#include "pthread.h"
#include "stdlib.h"
#include "unistd.h"
#include "signal.h"
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>


#define BUFFSIZE 10240 //Buffersize for the character arrays used.
#define COMMANDSIZE 5
#define TIMEOUT 100000 //Timeout interval for the backup. In seconds

int errorCode = -1;
char errorMessage[200];
/*
	101: "failure in reading the first line, i.e. request\n"
	102: "failure in reading the second line, i.e. fpga number\n"
	103: "invalid fpga number\n"
	104: "invalid message/cannot read file size\n"
	105: "invalid file size\n"
	106: "invalid message/cannot parse the message. Message does not have correct structure\n"
	107: "invalid command. request does not exist\n"
*/

void error(const char *msg)
{
    perror(msg);
    exit(1);
}

/*  returns 1 iff str ends with suffix  */
int str_ends_with(const char * str, const char * suffix) {

  if( str == NULL || suffix == NULL )
    return 0;

  size_t str_len = strlen(str);
  size_t suffix_len = strlen(suffix);

  if(suffix_len > str_len)
    return 0;

  return 0 == strncmp( str + str_len - suffix_len, suffix, suffix_len );
}

void downloadFile(int sockfd, int fileSize, char* tmpBuf)
{
	FILE* fp = fopen("myBitFile.bit","w+b");
	int nbw = 0;
	int m;
	int ret;

	while (nbw < fileSize)
	{
		ret = read(sockfd, tmpBuf, BUFFSIZE);
		printf("receiving...%d", ret);
		if (ret < 0)
		{
			errorCode = 108;
			strcpy(errorMessage, "file transfer failed\n");
			fclose(fp);
			return NULL;
			break;
		}
		if (ret == 0) //TODOTODOTODODODODODODODODODODOD (n == 0) might be a special case; handle it
		{
			errorCode = 108;
			strcpy(errorMessage, "file transfer failed\n");
			fclose(fp);
			return NULL;
			break;
		}
		if ((nbw + ret) <= fileSize)
			m = fwrite(tmpBuf, sizeof(char), ret, fp);
		else
		{
			m = fwrite(tmpBuf, sizeof(char), (fileSize - nbw), fp);
			printf("this was the last chunk of write to file\n");
		}
		printf("writing...%d", m);
		if (m != ret && m != (fileSize - nbw))
		{
			printf("file transfer failed");
			errorCode = 108;
			strcpy(errorMessage, "file transfer failed\n");
			fclose(fp);
			return NULL;
			break;
		}
		nbw += m;
	}
	if (errorCode != 108)
	{
		printf("out of while loop... number of bytes written is: %d\n", nbw);
		printf("file received successfully\n");
		errorCode = -1;
	}
	fclose(fp);
}

int find_FPGA_number(int sockfd, char* tmpBuf)
{
	//if ( (tmpBuf == NULL) || tmpBuf[0] == 0))
	int fpga_number = 0;
	fpga_number = (int)tmpBuf[0] - '0';
	printf("FPGA Number is: %c\n", tmpBuf[0]);
	return fpga_number;
}

void find_macAddress(char* tmpBuf, char* r)
{
    int mac_address_integer[6];
    r[0] = 106;
    r[1] = 1;
    int i=0;
    char* pch;
    pch = strtok(tmpBuf, ":");
    while (pch != NULL)
    {
        mac_address_integer[i] = (int)strtol(pch, NULL, 16);
        r[i+2] = (mac_address_integer[i] & 0xFF);
        i++;
        pch = strtok(NULL, ":");
    }
}



int find_fileSize(char* tmpBuf)
{
	int fileSizeInt = atoi(tmpBuf);
	printf("FILE SIZE is: %d\n", fileSizeInt);
	//printf("tmpBuf is: %s\n", tmpBuf);
	return fileSizeInt;
}

int readLine(int sock, char *line, int maxLineSize)
{
	int i = 0, crDetected = 0;
	while (1)
	{
		char c[10];
		int n = read(sock, c, 1);
		if (n > 0)
		{
			if (c[0] != '\r' && !crDetected)
			{
				line[i++] = c[0];
				if (i >= (maxLineSize - 1))
				{
					line[i] = 0;//truncate the line
					return 0;//failure
				}
			}
			else if (c[0] == '\r')
			{
				crDetected = 1;
			}
			else if (c[0] == '\n' && crDetected)
			{
				line[i] = 0;
				return 1;//success;	
			}
			else if (c[0] != '\r' && c[0] != '\n' && crDetected)
			{//strange situation. return error
				return 0;//failure
			}
		}
		if (n == 0)
		{//socket closed. truncate the line and return;
			line[i] = 0;
			return 1;//success
		}
		if (n < 0)
		{//socket error?
			return 0;//failure
		}
	}
	return 0;//failure;
}

int getReadCount(int fpgaNumber)
{
        char line[100];
		char *pch;
		int result = -2;
		
		char selectmapFile[100] = "/proc/fpga/selectmap";
		char filenumber[1];
		sprintf(filenumber, "%d", fpgaNumber);
		strncat(selectmapFile, filenumber, 1);
		
        FILE* fp = fopen(selectmapFile, "rb");
        if (fp == NULL)
        {
			printf("Unable to open /proc/fpga/selectmap[fpgaNumber]\n");
			return -3; //error
        }

        while(fgets(line, 100, fp))
        {
            if (strncmp(line, "Mode:", 5) == 0)
			{
				pch = strtok(line, " ");
				pch = strtok(NULL, " ");
				if (!(strncmp(pch, "FIFO", 4) == 0))
				{
					fclose(fp);
					return -1;
				}
			}
			
			if (strncmp(line, "Read count:", 11) == 0)
			{
				//printf("Yes; Here is the line: %s", line);
				pch = strtok(line, " ");
				pch = strtok(NULL, " ");
				pch = strtok(NULL, " ");
				//printf("your TOK is: %s", pch);
				result = atoi(pch);
				//printf("Result is: %d\n", result);
				fclose(fp);
				return result;;
			}
			//else
				//printf("No. It is not Read count. It is: %s", line);
        }
        fclose(fp);	
		return result;
}

int procSETMAC(char* myMacs, int fpgaNumber, int fpgaPortNumber)
{
	char deviceHandler[100] = "/dev/selectmap";
	char filenumber[1];
	sprintf(filenumber, "%d", fpgaNumber);
	strncat(deviceHandler, filenumber, 1);
	
	myMacs[1] = (fpgaPortNumber & 0xFF);
	
	int i = 0, res_status;
	int numWaiting = getReadCount(fpgaNumber);
	printf("number of getReadCount (numWaiting) is: %d\n", numWaiting);
	if (numWaiting < 0)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
		printf("numWaiting is < 0\n");
		return 1;
	}
	else if (numWaiting > 129)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
		printf("numWaiting is > 129\n");
		return 1;
	}
	
	unsigned char buf[100];
	FILE *fp = fopen(deviceHandler, "rb");
	if (fp == NULL)
	{
		printf("error in opening the file /dev/selectmap\n");
		return -1;//failure
	}
	while(numWaiting)
	{
		fread(buf, sizeof(char), 1, fp);
		printf("Read Value from /dev/sselectmap2 =  %x\n", buf[0]);
		numWaiting = getReadCount(fpgaNumber);
		printf("inside while(numWaiting) and numWaiting is = %d\n", numWaiting);
	}
	fclose(fp);
	
	printf("Drained lingering values from selectmap\n");
	
	//Send request for data
	//system("echo -n -e \\x49 > /dev/selectmap2");
	fp = fopen(deviceHandler, "wb");
	int m = -1;
	//{x6a, x01, x23, x45, x67, x89, xab, xcd}
	//char byte[8] = {106, 1, 35, 69, 103, 137, 171, 205};
	//m = fwrite(&byte[0], sizeof(byte), 8, fp);
	m = fwrite(&myMacs[0], 8, 8, fp);
	fclose(fp);
	
	printf("Sent 106 (x6a) to the selectmap\n");
	
	while (i < 100)
	{
		usleep(100000);
		printf("inside the loop and i is %d\n", i);
		if(numWaiting = getReadCount(fpgaNumber))
		{
			printf("inside the loop and numWaiting is = %d\n", numWaiting);
			fp = fopen(deviceHandler, "rb");
			fread(buf, sizeof(char), 1, fp);
			if (buf[0] == 107)
			{
				printf("Received response from fpga\n");
				res_status = 0;
			}
			else
			{
				buf[1] = 107;
				printf("Received incorrect response from fpga. buf[0] is = %x and buf[1] is = %x\n", buf[0], buf[1]);
				res_status = 1;
			}
		}
		i = i + 1;
		if (numWaiting)
			break;
	}
	
	if(!numWaiting) 
	{	
		printf("Did not receive a response from the fpga\n");
		res_status = 2;
    }
    fclose(fp);
	    
    printf("STATUS: pinging selectmap2 returned status %d.\n", res_status);

    if(res_status == 0)
	{
		//sendMessage ($sock, getType ("STATUS_RSP"), pack ("n", $res_status));
		printf("STATUS_RSP\n");
    }
	else if (res_status == 1)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_INVALID"), pack ("n", $res_status));
		printf("STATUS_ERR_INVALID\n");
    }
	else if (res_status == 2)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
		printf("STATUS_ERR_TIMEOUT\n");
    }
	
}


int procSTATUS(int fpgaNumber)
{
	int i = 0, res_status;
	char deviceHandler[100] = "/dev/selectmap";
	char filenumber[1];
	sprintf(filenumber, "%d", fpgaNumber);
	strncat(deviceHandler, filenumber, 1);
	
	int numWaiting = getReadCount(fpgaNumber);
	printf("number of getReadCount (numWaiting) is: %d\n", numWaiting);
	if (numWaiting < 0)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
		printf("numWaiting is < 0\n");
		if (numWaiting == -1)
		{
			printf("FPGA is not in FIFO mode. STATUS_ERR_TIMEOUT\n");
			return -2;
		}
		if (numWaiting == -3)
		{
			printf("Unable to open /proc/fpga/selectmap[fpgaNumber]. Try again. STATUS_ERR_TIMEOUT\n");
			return -3;
		}
		return 2;
	}
	else if (numWaiting > 129)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
		printf("numWaiting is > 129\n");
		return 2;
	}
	
	unsigned char buf[100];
	FILE *fp = fopen(deviceHandler, "rb");
	if (fp == NULL)
	{
		printf("error in opening the file /dev/selectmap[fpgaNumber]\n");
		return -1;//failure
	}
	while(numWaiting)
	{
		fread(buf, sizeof(char), 1, fp);
		printf("Read Value from /dev/selectmap[fpgaNumber] =  %x\n", buf[0]);
		numWaiting = getReadCount(fpgaNumber);
		if (numWaiting < 0)
		{
			//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
			printf("numWaiting is < 0\n");
			if (numWaiting == -1)
			{
				printf("FPGA is not in FIFO mode. STATUS_ERR_TIMEOUT\n");
				return -2;
			}
			if (numWaiting == -3)
			{
				printf("Unable to open /proc/fpga/selectmap[fpgaNumber]. Try again. STATUS_ERR_TIMEOUT\n");
				return -3;
			}
			return 2;
		}
		else if (numWaiting > 129)
		{
			//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
			printf("numWaiting is > 129\n");
			return 2;
		}
		printf("inside while(numWaiting) and numWaiting is = %d\n", numWaiting);
	}
	fclose(fp);
	
	printf("Drained lingering values from selectmap\n");
	
	//Send request for data
	//system("echo -n -e \\x49 > /dev/selectmap2");
	fp = fopen(deviceHandler, "wb");
	if (fp == NULL)
	{
		printf("error in opening the file /dev/selectmap[fpgaNumber]\n");
		return -1;//failure
	}
	int m = -1;
	char byte[2] = {49, 49};
	m = fwrite(&byte[0], sizeof(byte), 1, fp);
	fclose(fp);
	
	printf("Sent 49 to the selectmap\n");
	
	while (i < 100)
	{
		usleep(100000);
		printf("inside the loop and i is %d\n", i);
		if(numWaiting = getReadCount(fpgaNumber))
		{
			printf("inside the loop and numWaiting is = %d\n", numWaiting);
			
			if (numWaiting < 0)
			{
				//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
				printf("numWaiting is < 0\n");
				if (numWaiting == -1)
				{
					printf("FPGA is not in FIFO mode. STATUS_ERR_TIMEOUT\n");
					return -2;
				}
				if (numWaiting == -3)
				{
					printf("Unable to open /proc/fpga/selectmap[fpgaNumber]. Try again. STATUS_ERR_TIMEOUT\n");
					return -3;
				}
				return 2;
			}
			else if (numWaiting > 129)
			{
				//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
				printf("numWaiting is > 129\n");
				return 2;
			}
			
			fp = fopen(deviceHandler, "rb");
			if (fp == NULL)
			{
				printf("error in opening the file /dev/selectmap[fpgaNumber]\n");
				return -1;//failure
			}
			fread(buf, sizeof(char), 1, fp);
			if (buf[0] == 45)
			{
				printf("Received response from fpga\n");
				res_status = 0;
			}
			else
			{
				//buf[1] = 45;
				printf("Received incorrect response from fpga. buf[0] is = %x\n", buf[0]);
				res_status = 1;
			}
			fclose(fp);
		}
		i = i + 1;
		if (numWaiting)
			break;
	}
	
	if(!numWaiting) 
	{	
		printf("Did not receive a response from the fpga\n");
		res_status = 2;
    }
	//if (fp != NULL)
	//fclose(fp);
	    
    printf("STATUS: pinging selectmap[fpgaNumber] returned status %d.\n", res_status);

    if(res_status == 0)
	{
		//sendMessage ($sock, getType ("STATUS_RSP"), pack ("n", $res_status));
		printf("STATUS_RSP\n");
    }
	else if (res_status == 1)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_INVALID"), pack ("n", $res_status));
		printf("STATUS_ERR_INVALID\n");
    }
	else if (res_status == 2)
	{
		//sendMessage ($sock, getType ("STATUS_ERR_TIMEOUT"), pack ("n", 1));
		printf("STATUS_ERR_TIMEOUT\n");
    }
	return res_status;
}


/*
Thread which handles the incoming TCP connections
*/
void *processUnsequreRequest( void *var )
{
	char tmpBuf[BUFFSIZE];
	bzero(tmpBuf, BUFFSIZE);
	int fileSize = -1, fpgaNumber = -1, fpgaPortNumber = -1;
	int sockfd = (int)var;
	int n, m, cmd, res_status;
	char line[10];
	char macAddress[12];
	
	FILE *fpSelectmap;
	FILE *fpBitFile;
	FILE *fpdev;

	char filename[100];// = "/proc/fpga/selectmap";
	char filenamedev[100];
	char systemCall_1[100] = "echo 00000000 > /proc/fpga/selectmap";
	char systemCall_2[100] = "echo 04000000 > /proc/fpga/selectmap";
	char systemCall_3[100] = "cat default.bit > /dev/selectmap";
	char systemCall_4[100] = "echo 0f000000 > /proc/fpga/selectmap";
	
	char filenumber[1];

	printf("In thread\n");

	n = readLine(sockfd, tmpBuf, 20);
	if (n == 0)
	{
		printf("failure in reading the first line, i.e. request\n");
		errorCode = 101;
		strcpy(errorMessage, "failure in reading the first line, i.e. request\n");
		m = write(sockfd,"NOK\r\nfailure in reading the first line, i.e. request\r\n\r\n", 56);
		if (m < 0) error("ERROR writing to socket");
		close(sockfd);
		return NULL;
	}
	if (strncmp( tmpBuf, "GET", 3) == 0)
		cmd = 1;
	else if (strncmp( tmpBuf, "REL", 3) == 0)
		cmd = 2;
	else if (strncmp( tmpBuf, "RST", 3) == 0)
		cmd = 3;
	else if (strncmp( tmpBuf, "PRG", 3) == 0)
		cmd = 4;
	else if (strncmp( tmpBuf, "STA", 3) == 0)
		cmd = 5;
	else if (strncmp( tmpBuf, "MAC", 3) == 0)
		cmd = 6;
	else cmd = -1;
	
	switch (cmd)
	{
		case 1: //"GET":
			printf("Received command is resource_get\n");
			
			// ******************* FOR_FPGA_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the second line, i.e. fpga number\n");
				errorCode = 102;
				strcpy(errorMessage, "failure in reading the second line, i.e. fpga number\n");
				m = write(sockfd,"NOK\r\nfailure in reading the second line, i.e. fpga number\r\n\r\n", 61);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaNumber < 0 || fpgaNumber > 4) //there is an error
			{
				errorCode = 103;
				strcpy(errorMessage, "invalid fpga number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga number\n\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			sprintf(filenumber, "%d", fpgaNumber);
			
			strncat(systemCall_1, filenumber, 1);
			strncat(systemCall_2, filenumber, 1);
			strncat(systemCall_3, filenumber, 1);
			strncat(systemCall_4, filenumber, 1);
			
			system(systemCall_1);
			system(systemCall_2);
			system(systemCall_3);
			system(systemCall_4);
			
			printf("OK: get successfull\n");
			m = write(sockfd,"OK\r\nGet Successfull\r\n\r\n", 23);
			if (m < 0) error("ERROR writing to socket");
			close(sockfd);
			//return NULL;
			break;
			
			
		case 2: //"REL":
			printf("Received command is resource_release\n");
			//TODO: do whatever is needed for resource_release
			
			// ******************* FOR_FPGA_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the second line, i.e. fpga number\n");
				errorCode = 102;
				strcpy(errorMessage, "failure in reading the second line, i.e. fpga number\n");
				m = write(sockfd,"NOK\r\nfailure in reading the second line, i.e. fpga number\r\n\r\n", 61);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaNumber < 0 || fpgaNumber > 4) //there is an error
			{
				errorCode = 103;
				strcpy(errorMessage, "invalid fpga number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga number\n\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			
			
			sprintf(filenumber, "%d", fpgaNumber);
			
			strncat(systemCall_1, filenumber, 1);
			strncat(systemCall_2, filenumber, 1);
			strncat(systemCall_3, filenumber, 1);
			strncat(systemCall_4, filenumber, 1);
			
			system(systemCall_1);
			system(systemCall_2);
			system(systemCall_3);
			system(systemCall_4);
			
			printf("OK: release successfull\n");
			m = write(sockfd,"OK\r\nRelease Successfull\r\n\r\n", 27);
			
			if (m < 0) error("ERROR writing to socket");
			close(sockfd);
			//return NULL;
			break;
			
			
		case 3: //"RST":
			printf("Received command is resource_reset\n");
			//TODO: do whatever is needed for resource_reset
			
			// ******************* FOR_FPGA_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the second line, i.e. fpga number\n");
				errorCode = 102;
				strcpy(errorMessage, "failure in reading the second line, i.e. fpga number\n");
				m = write(sockfd,"NOK\r\nfailure in reading the second line, i.e. fpga number\r\n\r\n", 61);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaNumber < 0 || fpgaNumber > 4) //there is an error
			{
				errorCode = 103;
				strcpy(errorMessage, "invalid fpga number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga number\n\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			
			sprintf(filenumber, "%d", fpgaNumber);
			
			strncat(systemCall_1, filenumber, 1);
			strncat(systemCall_2, filenumber, 1);
			strncat(systemCall_3, filenumber, 1);
			strncat(systemCall_4, filenumber, 1);
			
			system(systemCall_1);
			system(systemCall_2);
			system(systemCall_3);
			system(systemCall_4);
			
			printf("OK: reset successfull\n");
			m = write(sockfd,"OK\r\nReset Successfull\r\n\r\n", 25);
			
			if (m < 0) error("ERROR writing to socket");
			close(sockfd);
			//return NULL;
			break;
			
			
		case 4: //"PRG":
			printf("Received command is resource_program\n");
			//TODO: do whatever is needed for resource_program
			
			// ******************* FOR_FPGA_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the second line, i.e. fpga number\n");
				errorCode = 102;
				strcpy(errorMessage, "failure in reading the second line, i.e. fpga number\n");
				m = write(sockfd,"NOK\r\nfailure in reading the second line, i.e. fpga number\r\n\r\n", 61);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaNumber < 0 || fpgaNumber > 4) //there is an error
			{
				errorCode = 103;
				strcpy(errorMessage, "invalid fpga number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga number\n\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			// ******************** FOR_FILE_SIZE **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n  == 0)
			{
				//TODO: errorCode should be set to "invalid message/cannot read file size. message is too short".
				printf("invalid message/cannot read file size\n");
				errorCode = 104;
				strcpy(errorMessage, "invalid message/cannot read file size\n");
				m = write(sockfd,"NOK\r\ninvalid message/cannot read file size\r\n\r\n", 41);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fileSize = find_fileSize(tmpBuf);
			
			if (fileSize <=0) //there is an error
			{
				printf("invalid file size\n");
				errorCode = 105;
				strcpy(errorMessage, "invalid file size\n");
				m = write(sockfd,"NOK\r\ninvalid file size\r\n\r\n", 26);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// **********************************************************
			
			n = readLine(sockfd, tmpBuf, 20);//This is for reading the extra \r\n in protocol which indicates end of message
			if (n  == 0)
			{
				printf("invalid message/cannot parse the message. Message does not have correct structure\n");
				errorCode = 106;
				strcpy(errorMessage, "invalid message/cannot parse the message. Message does not have correct structure\n");
				m = write(sockfd,"NOK\r\ninvalid message/cannot parse the message. Message does not have correct structure\r\n\r\n", 90);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
				break;
			}
			downloadFile(sockfd, fileSize, tmpBuf);
			if (errorCode == 108)
			{
				printf("NOK: file transfer failed\n");
				m = write(sockfd,"NOK\r\nfile transfer failed\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
				break;
			}
			
			sprintf(filenumber, "%d", fpgaNumber);
			
			strncat(systemCall_1, filenumber, 1);
			strncat(systemCall_2, filenumber, 1);
			bzero(systemCall_3, 100);
			//strcpy(systemCall_3, "cat myBitFile.bit > /dev/selectmap");
			strcpy(systemCall_3, "cat default.bit > /dev/selectmap");
			strncat(systemCall_3, filenumber, 1);
			strncat(systemCall_4, filenumber, 1);
			
			system(systemCall_1);
			system(systemCall_2);
			system(systemCall_3);
			system(systemCall_4);
			
			printf("OK: program successfull\n");
			m = write(sockfd,"OK\r\nProgram Successfull\r\n\r\n", 27);
			if (m < 0) error("ERROR writing to socket");
			close(sockfd);
			//return NULL;
			break;
			
		
		case 5: //"STA":
			printf("Received command is resource_status\n");
			
			// ******************* FOR_FPGA_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the second line, i.e. fpga number\n");
				errorCode = 102;
				strcpy(errorMessage, "failure in reading the second line, i.e. fpga number\n");
				m = write(sockfd,"NOK\r\nfailure in reading the second line, i.e. fpga number\r\n\r\n", 61);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaNumber < 0 || fpgaNumber > 4) //there is an error
			{
				errorCode = 103;
				strcpy(errorMessage, "invalid fpga number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga number\n\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			res_status = procSTATUS(fpgaNumber);
			char msg[200];
			switch (res_status)
			{
				case -1:
					strcpy(msg, "NOK\r\nerror in opening the file /dev/selectmap[fpgaNumber]. STATUS_ERR_TIMEOUT. STATUS is not available. Try again.\r\n\r\n");
					m = write(sockfd, msg, 118);
					if (m < 0) error("ERROR writing to socket");
					close(sockfd);					
					break;
				case -2:
					strcpy(msg, "NOK\r\nFPGA is not in FIFO mode. STATUS_ERR_TIMEOUT\r\n\r\n");
					m = write(sockfd, msg, 53);
					if (m < 0) error("ERROR writing to socket");
					close(sockfd);				
					break;
				case -3:
					strcpy(msg, "NOK\r\nerror in opening the file /proc/fpga/selectmap[fpgaNumber]. STATUS_ERR_TIMEOUT. STATUS is not available. Try again.\r\n\r\n");
					m = write(sockfd, msg, 124);
					if (m < 0) error("ERROR writing to socket");
					close(sockfd);
					break;
				case 0:
					strcpy(msg, "OK\r\nSTATUS_RSP\r\n\r\n");
					m = write(sockfd, msg, 18);
					if (m < 0) error("ERROR writing to socket");
					close(sockfd);
					break;
				case 1:
					strcpy(msg, "NOK\r\nSTATUS_ERR_INVALID\r\n\r\n");
					m = write(sockfd, msg, 27);
					if (m < 0) error("ERROR writing to socket");
					close(sockfd);
					break;
				case 2:
					strcpy(msg, "NOK\r\nSTATUS_ERR_TIMEOUT\r\n\r\n");
					m = write(sockfd, msg, 27);
					if (m < 0) error("ERROR writing to socket");
					close(sockfd);
					break;
				default:
					break;
			}
			
			//m = write(sockfd, msg, 23);
			//if (m < 0) error("ERROR writing to socket");
			//close(sockfd);
			
			//return NULL;
			break;


		case 6: //"MAC":
			printf("Received command is resource_set_mac\n");
			//TODO: do whatever is needed for resource_set_mac
			
			// ******************* FOR_FPGA_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the second line, i.e. fpga number\n");
				errorCode = 102;
				strcpy(errorMessage, "failure in reading the second line, i.e. fpga number\n");
				m = write(sockfd,"NOK\r\nfailure in reading the second line, i.e. fpga number\r\n\r\n", 61);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaNumber < 0 || fpgaNumber > 4) //there is an error
			{
				errorCode = 103;
				strcpy(errorMessage, "invalid fpga number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga number\n\r\n\r\n", 29);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			// ******************** FOR_MAC_ADDRESS **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n  == 0)
			{
				//TODO: errorCode should be set to "invalid message/cannot read file size. message is too short".
				printf("invalid message/cannot read MAC address\n");
				errorCode = 104;
				strcpy(errorMessage, "invalid message/cannot read MAC address\n");
				m = write(sockfd,"NOK\r\ninvalid message/cannot read MAC address\r\n\r\n", 48);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			char resMAC[8];
			bzero(resMAC, 8);
			find_macAddress(tmpBuf, resMAC);
			
			//TODODODODODODOD add something to be returned by find_macAddress funstion to handle errors
			/*
			if (fileSize <=0) //there is an error
			{
				printf("invalid file size\n");
				errorCode = 105;
				strcpy(errorMessage, "invalid file size\n");
				m = write(sockfd,"NOK\r\ninvalid file size\r\n\r\n", 26);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			*/
			
			// **********************************************************
			
			n = readLine(sockfd, tmpBuf, 20);//This is for reading the extra \r\n in protocol which indicates end of message
			if (n  == 0)
			{
				printf("invalid message/cannot parse the message. Message does not have correct structure\n");
				errorCode = 106;
				strcpy(errorMessage, "invalid message/cannot parse the message. Message does not have correct structure\n");
				m = write(sockfd,"NOK\r\ninvalid message/cannot parse the message. Message does not have correct structure\r\n\r\n", 90);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
				break;
			}
			
			// ******************* FOR_FPGA_PORT_NUMBER **********************
			n = readLine(sockfd, tmpBuf, 20);
			if (n == 0)
			{
				printf("failure in reading the port_number line\n");
				errorCode = 102; //TODO: fix this error code
				strcpy(errorMessage, "failure in reading the port_number line\n");
				m = write(sockfd,"NOK\r\nfailure in reading the port_number line\r\n\r\n", 48);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			fpgaPortNumber = find_FPGA_number(sockfd, tmpBuf);

			if (fpgaPortNumber < 0 || fpgaPortNumber > 4) //there is an error
			{
				errorCode = 103; //TODO: fix this error code
				strcpy(errorMessage, "invalid fpga port number\n");
				m = write(sockfd,"NOK\r\ninvalid fpga port number\n\r\n\r\n", 34);
				if (m < 0) error("ERROR writing to socket");
				close(sockfd);
				printf("\n\n\n\nAwaiting for a new request from the client\n");
				return NULL;
			}
			// *********************************************************
			
			procSETMAC(resMAC, fpgaNumber, fpgaPortNumber);
			
			printf("OK: mac set successfull\n");
			m = write(sockfd,"OK\r\nMAC-SET Successfull\r\n\r\n", 27);
			if (m < 0) error("ERROR writing to socket");
			close(sockfd);
			break;
			
					
			
		
		case -1: //"BAD COMMAND":
		
			printf("invalid command. request does not exist\n");
			errorCode = 107;
			strcpy(errorMessage, "invalid command. request does not exist\n");
			m = write(sockfd,"NOK\r\ninvalid command. request does not exist\r\n\r\n", 43);
			if (m < 0) error("ERROR writing to socket");
			close(sockfd);
			//return NULL;
			break;
		default:
			break;
	}
	printf("\n\n\n\nAwaiting for a new request from the client\n");
	return NULL;
}


int main(int argc, char *argv[])
{
     int sockfd, newsockfd, portno, optval;
     socklen_t clilen;
     pthread_t incomingConnection;
     char buffer[256];
     struct sockaddr_in serv_addr, cli_addr;
     int n;

     portno = 6677;

     if (argc == 2) {
        portno = atoi(argv[1]);
     }
     sockfd = socket(AF_INET, SOCK_STREAM, 0);
     if (sockfd < 0)
        error("ERROR opening socket");
     bzero((char *) &serv_addr, sizeof(serv_addr));
     serv_addr.sin_family = AF_INET;
     serv_addr.sin_addr.s_addr = INADDR_ANY;
     serv_addr.sin_port = htons(portno);
     optval = 1;
     setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval));
     if (bind(sockfd, (struct sockaddr *) &serv_addr,
              sizeof(serv_addr)) < 0)
              error("ERROR on binding");
     listen(sockfd,5);
     clilen = sizeof(cli_addr);
	int acceptedSocks[100];
	int aSockIdx = 0;
	while (1)
	{
     		newsockfd = accept(sockfd,
                	 (struct sockaddr *) &cli_addr,
                 		&clilen);
     		if (newsockfd < 0)
          		error("ERROR on accept");
		acceptedSocks[aSockIdx] = newsockfd;

		pthread_create( &incomingConnection, NULL, processUnsequreRequest, (void*) acceptedSocks[aSockIdx] );
		aSockIdx ++;
		aSockIdx %= 100;
		pthread_detach ( incomingConnection );
	}
	
	close(sockfd);
	return 0;
}


