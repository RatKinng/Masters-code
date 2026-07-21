#include <Arduino_FreeRTOS.h>
#include <semphr.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <avr/wdt.h>
#include <avr/io.h>

// MPU6050
Adafruit_MPU6050 mpu;

// SRAM Limits
#define SRAM_START 0x0100
#define SRAM_END   0x21FF

// Task Declarations
void TaskAnalogRead(void *pvParameters);
void TaskFlipBit(void *pvParameters);
void TaskMPU(void *pvParameters);
void TaskLogger(void *pvParameters);
void TaskSerialCommand(void *pvParameters);

// Function Declarations
uintptr_t clampToSRAM(uintptr_t addr);
void softwareRestart();

uint32_t getUptimeMs();

// Mutexes
SemaphoreHandle_t xI2CMutex;
SemaphoreHandle_t xSerialMutex;
SemaphoreHandle_t xLogMutex;

// Dedicated corruption buffer
uint8_t testBuffer[128];

volatile uintptr_t currentTargetAddress = (uintptr_t)testBuffer;

char serialBuffer[16];
uint8_t serialIndex = 0;

// Reset Tracking
uint8_t resetCause;

// Logging Structure
typedef struct{
  uint32_t uptimeMs;
  int analogValue;
  float accelX;
  float accelY;
  float accelZ;
  float gyroX;
  float gyroY;
  float gyroZ;
  float temperature;
} SystemLogRecord;

SystemLogRecord gLog;

// Utility Functions
uint32_t getUptimeMs(){
  TickType_t ticks = xTaskGetTickCount();
  return ((uint32_t)ticks * portTICK_PERIOD_MS);
}

uintptr_t clampToSRAM(uintptr_t addr){
  if (addr < SRAM_START)
    return SRAM_START;

  if (addr > SRAM_END)
    return SRAM_START;

  return addr;
}

void softwareRestart(){
  xSemaphoreTake(xSerialMutex, portMAX_DELAY);

  Serial.println();
  Serial.println("Software restart requested...");
  Serial.flush();

  xSemaphoreGive(xSerialMutex);

  taskDISABLE_INTERRUPTS();

  wdt_enable(WDTO_15MS);

  while (1){
    // Wait for watchdog reset
  }
}

// Setup
void setup(){
  resetCause = MCUSR;
  MCUSR = 0;
  wdt_disable();

  Serial.begin(115200);

  while (!Serial){;}

  randomSeed(analogRead(A15));
  xI2CMutex = xSemaphoreCreateMutex();
  xSerialMutex = xSemaphoreCreateMutex();
  xLogMutex = xSemaphoreCreateMutex();

  if (xI2CMutex == NULL || xSerialMutex == NULL || xLogMutex == NULL){
    while (1){}
  }

  xSemaphoreTake(xSerialMutex, portMAX_DELAY);
  Serial.println();
  Serial.println("REBOOT -----------------------------------");

  if (resetCause & _BV(WDRF)){
    Serial.println("Reset Cause: WATCHDOG");
  }
  else if (resetCause & _BV(PORF)){
    Serial.println("Reset Cause: POWER ON");
  }
  else if (resetCause & _BV(EXTRF)){
    Serial.println("Reset Cause: EXTERNAL RESET");
  }
  else if (resetCause & _BV(BORF)){
    Serial.println("Reset Cause: BROWNOUT");
  }
  else{
    Serial.println("Reset Cause: UNKNOWN");
  }

  xSemaphoreGive(xSerialMutex);

  // MPU6050 Initialization
  xSemaphoreTake(xI2CMutex, portMAX_DELAY);
  bool mpuStatus = mpu.begin();
  xSemaphoreGive(xI2CMutex);

  if (!mpuStatus){
    xSemaphoreTake(xSerialMutex, portMAX_DELAY);
    Serial.println("Failed to find MPU6050 chip");
    xSemaphoreGive(xSerialMutex);

    while (1){
      vTaskDelay(pdMS_TO_TICKS(100));
    }
  }

  xSemaphoreTake(xI2CMutex, portMAX_DELAY);
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  xSemaphoreGive(xI2CMutex);

  xSemaphoreTake(xSerialMutex, portMAX_DELAY);
  Serial.println("MPU6050 Found!");
  xSemaphoreGive(xSerialMutex);

  // Create Tasks
  xTaskCreate(TaskAnalogRead, "AnalogRead", 256, NULL, 1, NULL);
  xTaskCreate(TaskFlipBit, "FlipBit", 256, NULL, 1, NULL);
  xTaskCreate(TaskMPU, "MPU", 768, NULL, 2, NULL);
  xTaskCreate(TaskLogger, "Logger", 512, NULL, 1, NULL);
  xTaskCreate(TaskSerialCommand, "SerialCmd", 256, NULL, 1, NULL);
}

void loop(){}

// Analog Task
void TaskAnalogRead(void *pvParameters){
  (void)pvParameters;
  for (;;){
    int sensorValue = analogRead(A0);
    xSemaphoreTake(xLogMutex, portMAX_DELAY);

    gLog.analogValue = sensorValue;
    gLog.uptimeMs = getUptimeMs();

    xSemaphoreGive(xLogMutex);

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// MPU Task
void TaskMPU(void *pvParameters){
  (void)pvParameters;

  sensors_event_t a, g, temp;
  for (;;){
    xSemaphoreTake(xI2CMutex, portMAX_DELAY);
    mpu.getEvent(&a, &g, &temp);
    xSemaphoreGive(xI2CMutex);

    xSemaphoreTake(xLogMutex, portMAX_DELAY);

    gLog.accelX = a.acceleration.x;
    gLog.accelY = a.acceleration.y;
    gLog.accelZ = a.acceleration.z;

    gLog.gyroX = g.gyro.x;
    gLog.gyroY = g.gyro.y;
    gLog.gyroZ = g.gyro.z;

    gLog.temperature = temp.temperature;

    xSemaphoreGive(xLogMutex);

    vTaskDelay(pdMS_TO_TICKS(500));
  }
}

// Bit Flip Task
void TaskFlipBit(void *pvParameters){
  (void)pvParameters;

  for (;;){
    uintptr_t addr;

    taskENTER_CRITICAL();
    addr = clampToSRAM(currentTargetAddress);
    taskEXIT_CRITICAL();

    if (addr >= SRAM_START && addr <= SRAM_END){
      uint8_t *targetByte = (uint8_t *)addr;
      uint8_t bitIndex = random(8);
      
      xSemaphoreTake( xSerialMutex, portMAX_DELAY);

      Serial.print("FLIP @ 0x");
      Serial.print((unsigned int)addr, HEX);
      Serial.print(" bit ");
      Serial.println(bitIndex);

      xSemaphoreGive( xSerialMutex);
      
      *targetByte ^= (1 << bitIndex);
    }

    taskENTER_CRITICAL();
    currentTargetAddress++;

    if (currentTargetAddress > SRAM_END) {
      currentTargetAddress = SRAM_START;
    }

    taskEXIT_CRITICAL();
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// Logger Task
void TaskLogger(void *pvParameters){
  (void)pvParameters;
  for (;;){
    xSemaphoreTake(xLogMutex, portMAX_DELAY);

    uint32_t uptime = gLog.uptimeMs;
    int analogValue = gLog.analogValue;

    float accelX = gLog.accelX;
    float accelY = gLog.accelY;
    float accelZ = gLog.accelZ;

    float gyroX = gLog.gyroX;
    float gyroY = gLog.gyroY;
    float gyroZ = gLog.gyroZ;

    float temperature = gLog.temperature;

    xSemaphoreGive(xLogMutex);

    xSemaphoreTake(xSerialMutex, portMAX_DELAY);

    Serial.print("Uptime: ");
    Serial.print(uptime);

    Serial.print(" | Analog: ");
    Serial.print(analogValue);

    Serial.print(" | Accel: ");
    Serial.print(accelX, 3);
    Serial.print(",");
    Serial.print(accelY, 3);
    Serial.print(",");
    Serial.print(accelZ, 3);

    Serial.print(" | Gyro: ");
    Serial.print(gyroX, 3);
    Serial.print(",");
    Serial.print(gyroY, 3);
    Serial.print(",");
    Serial.print(gyroZ, 3);

    Serial.print(" | Temp: ");
    Serial.println(temperature, 2);

    xSemaphoreGive(xSerialMutex);

    vTaskDelay(pdMS_TO_TICKS(300));
  }
}

// Serial Command Task
void TaskSerialCommand(void *pvParameters){
  (void)pvParameters;
  for (;;){
    while (Serial.available()){
      char c = Serial.read();

      if (c == '\n' || c == '\r'){
        if (serialIndex > 0){
          serialBuffer[serialIndex] = '\0';

          if (strcmp(serialBuffer, "restart") == 0) softwareRestart();
          else{
            uintptr_t newAddress;

            if (strncmp(serialBuffer, "0x", 2) == 0) newAddress = strtoul(serialBuffer, NULL, 16);
            else newAddress = strtoul(serialBuffer, NULL, 10);

            newAddress = clampToSRAM(newAddress);

            taskENTER_CRITICAL();
            currentTargetAddress = newAddress;
            taskEXIT_CRITICAL();

            xSemaphoreTake(xSerialMutex, portMAX_DELAY);

            Serial.print("New target address: 0x");
            Serial.println((unsigned int)newAddress, HEX);

            xSemaphoreGive(xSerialMutex);
          }
          serialIndex = 0;
        }
      }
      else{ if (serialIndex < sizeof(serialBuffer) - 1) serialBuffer[ serialIndex++] = c; }
    }

    vTaskDelay(pdMS_TO_TICKS(20));
  }
}



