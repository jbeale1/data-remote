// Read binary data from STDIN of 32-bit unsigned integers, print as decimal integer
// for example, from the binary file generated by
//   iio_readdev -u "ip:localhost" -b 256 -s 100 -T 0 ad7124-8 voltage0-voltage1 | adi_bin2csv
//
// 21-Sep-2022 J.Beale

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#define UI (unsigned int)

void main(int argc, char **argv ) {
  const int ws = 4;            // wordsize: how many bytes per word
  unsigned char buffer[ws];
  uint32_t raw;
  uint32_t b4, b3, b2, b1;
  size_t bytes_read;
  int p = 0;                 // pointer into buffer

  bytes_read = fread(buffer,sizeof(buffer[0]),4,stdin); // read 4 bytes
  while (bytes_read == ws) {
      b4 = buffer[p];
      b3 = buffer[p+1];
      b2 = buffer[p+2];
      b1 = buffer [p+3];
      raw = b4*(1<<24) + b3*(1<<16) + b2*(1<<8) + b1;
      printf("%d\n",raw);

      bytes_read = fread(buffer,sizeof(buffer[0]),4,stdin); // read 4 bytes
  };

}