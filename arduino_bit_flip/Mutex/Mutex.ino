#include <Arduino_FreeRTOS.h>
#include <semphr.h>
#include <avr/wdt.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// MPU6050 Object
Adafruit_MPU6050 mpu;

// FreeRTOS Task Declarations
void TaskAnalogRead(void *pvParameters);
void TaskFlipBit(void *pvParameters);
void TaskMPU(void *pvParameters);

// Semaphore Handles
SemaphoreHandle_t xI2CMutex;
SemaphoreHandle_t xSerialMutex;

// Timer Variables
volatile uint32_t millis32 = 0;

// Bit Flip Variables
size_t currentByte = 0;

// Dedicated corruption buffer
uint8_t testBuffer[128];

// Function Declarations
void corruptMemory(void *startPointer, int nBytes, unsigned long bitErrorRate);
void flipBit(void *startPointer, int nBytes);
void flipBitSequentialRandomBit(void *startPointer, size_t nBytes);

// Timer1 ISR
ISR(TIMER1_COMPA_vect) {
  millis32++;
}

// Setup Timer1 for 1ms Tick
void setupTimer1Millis() {
  cli();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  OCR1A = 1999;
  TCCR1B |= (1 << WGM12);
  TCCR1B |= (1 << CS11);
  TIMSK1 |= (1 << OCIE1A);

  sei();
}

// Setup
void setup() {
  Serial.begin(115200);

  while (!Serial) {;}

  // Create Mutexes
  xI2CMutex = xSemaphoreCreateMutex();
  xSerialMutex = xSemaphoreCreateMutex();

  if (xI2CMutex == NULL || xSerialMutex == NULL) {
    while (1);
  }

  // Serial Protected Print
  xSemaphoreTake(xSerialMutex, portMAX_DELAY);
  Serial.println("REBOOT -----------------------------------");
  xSemaphoreGive(xSerialMutex);

  // Initialize MPU6050
  xSemaphoreTake(xI2CMutex, portMAX_DELAY);
  bool mpuStatus = mpu.begin();
  xSemaphoreGive(xI2CMutex);

  if (!mpuStatus) {
    xSemaphoreTake(xSerialMutex, portMAX_DELAY);
    Serial.println("Failed to find MPU6050 chip");
    xSemaphoreGive(xSerialMutex);

    while (1) {
      vTaskDelay(pdMS_TO_TICKS(100));
    }
  }

  xSemaphoreTake(xSerialMutex, portMAX_DELAY);
  Serial.println("MPU6050 Found!");
  xSemaphoreGive(xSerialMutex);

  // Configure MPU6050
  xSemaphoreTake(xI2CMutex, portMAX_DELAY);

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  xSemaphoreGive(xI2CMutex);

  // Print MPU Configuration
  xSemaphoreTake(xSerialMutex, portMAX_DELAY);
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

  xSemaphoreGive(xSerialMutex);

  // Create Tasks
  xTaskCreate(TaskAnalogRead, "AnalogRead", 256, NULL, 1, NULL);
  xTaskCreate(TaskFlipBit, "FlipBit", 256, NULL, 1, NULL);
  xTaskCreate(TaskMPU, "MPU", 768, NULL, 2, NULL);
}

// Main Loop
void loop() {
  // Empty
}

// Analog Read Task
void TaskAnalogRead(void *pvParameters) {
  (void) pvParameters;
  for (;;) {
    int sensorValue = analogRead(A0);
    uint32_t uptime;

    noInterrupts();
    uptime = millis32;
    interrupts();

    xSemaphoreTake(xSerialMutex, portMAX_DELAY);

    Serial.print("Sensor: ");
    Serial.print(sensorValue);
    Serial.print(" | Uptime(ms): ");
    Serial.println(uptime);

    xSemaphoreGive(xSerialMutex);

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// Flip Bit Task
void TaskFlipBit(void *pvParameters) {
  (void) pvParameters;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(200));

    flipBitSequentialRandomBit(testBuffer, sizeof(testBuffer));
  }
}

// MPU6050 Task
void TaskMPU(void *pvParameters) {
  (void) pvParameters;
  sensors_event_t a, g, temp;

  for (;;) {
    // Protect I2C Bus
    xSemaphoreTake(xI2CMutex, portMAX_DELAY);
    mpu.getEvent(&a, &g, &temp);
    xSemaphoreGive(xI2CMutex);

    // Protect Serial Output
    xSemaphoreTake(xSerialMutex, portMAX_DELAY);

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

    xSemaphoreGive(xSerialMutex);

    vTaskDelay(pdMS_TO_TICKS(500));
  }
}

// Flip Bit Functions
void flipBit(void *startPointer, int nBytes) {
  uint8_t *ptr = (uint8_t *)startPointer;
  int byteIndex = random(nBytes);
  int bitIndex = random(8);
  uint8_t *targetByte = ptr + byteIndex;

  xSemaphoreTake(xSerialMutex, portMAX_DELAY);

  Serial.print("Flipping address ");
  Serial.print((uintptr_t)targetByte);
  Serial.print(", bit ");
  Serial.println(bitIndex);

  xSemaphoreGive(xSerialMutex);

  ptr[byteIndex] ^= (1 << bitIndex);
}

void flipBitSequentialRandomBit(void *startPointer, size_t nBytes) {
  if (nBytes == 0) {
    return;
  }

  uint8_t *ptr = (uint8_t *)startPointer;

  if (currentByte >= nBytes) {
    currentByte = 0;
  }

  uint8_t *targetByte = ptr + currentByte;
  uint8_t bitIndex = random(8);

  xSemaphoreTake(xSerialMutex, portMAX_DELAY);

  Serial.print("Flipping address ");
  Serial.print((uintptr_t)targetByte);
  Serial.print(", bit ");
  Serial.println(bitIndex);

  xSemaphoreGive(xSerialMutex);

  *targetByte ^= (1 << bitIndex);

  currentByte++;
}