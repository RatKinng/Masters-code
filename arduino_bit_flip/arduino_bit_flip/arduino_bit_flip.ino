#include <Arduino_FreeRTOS.h>
#include <avr/wdt.h>

// define three tasks for AnalogRead, and FlipBit
void TaskAnalogRead( void *pvParameters );
void TaskFlipBit(void *pvParameters);
void TaskMPU(void *pvParameters);

// Define corruptMemory function
void corruptMemory(void *startPointer,int nBytes,unsigned long bitErrorRate);

// --------- 32-bit Millisecond Timer Variables ----------
volatile uint32_t millis32 = 0;  // Uptime in milliseconds

size_t currentByte = 0;          // byte index for flipBitSequentialRandomBit

// Timer1 interrupt service routine
ISR(TIMER1_COMPA_vect) {
  millis32++;  // Increment millisecond counter
}

void setupTimer1Millis() {
  cli();                // Disable interrupts
  TCCR1A = 0;           // Normal operation
  TCCR1B = 0;
  TCNT1 = 0;            // Start counting from 0

  OCR1A = 1999;         // Compare match value for 1ms
  TCCR1B |= (1 << WGM12);  // CTC mode
  TCCR1B |= (1 << CS11);   // Prescaler = 8
  TIMSK1 |= (1 << OCIE1A); // Enable Timer1 Compare Interrupt
  sei();                // Enable interrupts
}

void setup() {
  Serial.begin(115200);
  while (!Serial)
    delay(10); // will pause Zero, Leonardo, etc until serial console opens

  Serial.println("REBOOT -----------------------------------");

  // // Timer for millis32
  // setupTimer1Millis();

  // Try to initialize!
  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip");
    while (1) {
      delay(10);
    }
  }
  Serial.println("MPU6050 Found!");

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  Serial.print("Accelerometer range set to: ");
  switch (mpu.getAccelerometerRange()) {
  case MPU6050_RANGE_2_G:
    Serial.println("+-2G");
    break;
  case MPU6050_RANGE_4_G:
    Serial.println("+-4G");
    break;
  case MPU6050_RANGE_8_G:
    Serial.println("+-8G");
    break;
  case MPU6050_RANGE_16_G:
    Serial.println("+-16G");
    break;
  }
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  Serial.print("Gyro range set to: ");
  switch (mpu.getGyroRange()) {
  case MPU6050_RANGE_250_DEG:
    Serial.println("+- 250 deg/s");
    break;
  case MPU6050_RANGE_500_DEG:
    Serial.println("+- 500 deg/s");
    break;
  case MPU6050_RANGE_1000_DEG:
    Serial.println("+- 1000 deg/s");
    break;
  case MPU6050_RANGE_2000_DEG:
    Serial.println("+- 2000 deg/s");
    break;
  }

  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.print("Filter bandwidth set to: ");
  switch (mpu.getFilterBandwidth()) {
  case MPU6050_BAND_260_HZ:
    Serial.println("260 Hz");
    break;
  case MPU6050_BAND_184_HZ:
    Serial.println("184 Hz");
    break;
  case MPU6050_BAND_94_HZ:
    Serial.println("94 Hz");
    break;
  case MPU6050_BAND_44_HZ:
    Serial.println("44 Hz");
    break;
  case MPU6050_BAND_21_HZ:
    Serial.println("21 Hz");
    break;
  case MPU6050_BAND_10_HZ:
    Serial.println("10 Hz");
    break;
  case MPU6050_BAND_5_HZ:
    Serial.println("5 Hz");
    break;
  }

  // // Create tasks
  xTaskCreate(TaskAnalogRead, "AnalogRead", 256, NULL, 1, NULL);
  xTaskCreate(TaskFlipBit, "FlipBit", 256, NULL, 2, NULL);
  xTaskCreate(TaskMPU, "MPU", 512, NULL, 2, NULL);
}

void loop() {
  // Empty. Things are done in Tasks. Never Block or delay.
}

/*--------------------------------------------------*/
/*---------------------- Tasks ---------------------*/
/*--------------------------------------------------*/

void TaskAnalogRead(void *pvParameters){ 
  (void) pvParameters;

  for (;;) {
    int sensorValue = analogRead(A0);

    // Access the uptime in milliseconds
    uint32_t uptime;
    noInterrupts();
    uptime = millis32;
    interrupts();

    Serial.print("Sensor: ");
    Serial.print(sensorValue);
    Serial.print(" | Uptime(ms): ");
    Serial.println(uptime);

    vTaskDelay(1); // one tick delay for stability
  }
}

void TaskFlipBit(void *pvParameters){
  (void) pvParameters;

  for (;;) {
    vTaskDelay(200);
    flipBitSequentialRandomBit(481, 10);
  }
}

void TaskMPU(void *pvParameters){
  /* Get new sensor events with the readings */
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  /* Print out the values */
  Serial.print("Acceleration X: ");
  Serial.print(a.acceleration.x);
  Serial.print(", Y: ");
  Serial.print(a.acceleration.y);
  Serial.print(", Z: ");
  Serial.print(a.acceleration.z);
  Serial.println(" m/s^2");

  Serial.print("Rotation X: ");
  Serial.print(g.gyro.x);
  Serial.print(", Y: ");
  Serial.print(g.gyro.y);
  Serial.print(", Z: ");
  Serial.print(g.gyro.z);
  Serial.println(" rad/s");

  Serial.print("Temperature: ");
  Serial.print(temp.temperature);
  Serial.println(" degC");

  Serial.println("");
  delay(500);


  
}

// ------------------------------------------------
// Flip bit functions (unchanged from your code)
// ------------------------------------------------

void flipBit(void *startPointer, int nBytes){
  uint8_t *ptr = (uint8_t *)startPointer;
  int byteIndex = random(nBytes);
  int bitIndex = random(8);
  
  uint8_t *targetByte = ptr + byteIndex;
  Serial.print("Flipping address ");
  Serial.print((uintptr_t)targetByte);
  Serial.print(", bit ");
  Serial.println(bitIndex);
  Serial.flush();

  ptr[byteIndex] ^= (1 << bitIndex);
}

void flipBitSequentialRandomBit(void *startPointer, size_t nBytes){
    if (nBytes == 0) return;

    uint8_t *ptr = (uint8_t *)startPointer;

    // Wrap if needed
    if (currentByte >= nBytes) currentByte = 0;

    uint8_t *targetByte = ptr + currentByte;
    uint8_t bitIndex = random(8);

    Serial.print("Flipping address ");
    Serial.print((uintptr_t)targetByte);
    Serial.print(", bit ");
    Serial.println(bitIndex);
    Serial.flush();

    *targetByte ^= (1 << bitIndex);

    // Advance to next byte
    currentByte++;
}


