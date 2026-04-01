#include <Arduino_FreeRTOS.h>
#include <avr/wdt.h>

// define three tasks for AnalogRead, and FlipBit
void TaskAnalogRead( void *pvParameters );
void TaskFlipBit(void *pvParameters);

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
    Serial.begin(9600);
    delay(100); // let UART initialize

    Serial.println("REBOOT -----------------------------------");

    // // Timer for millis32
    // setupTimer1Millis();

    // // Create tasks
    // xTaskCreate(TaskAnalogRead, "AnalogRead", 256, NULL, 1, NULL);
    // xTaskCreate(TaskFlipBit, "FlipBit", 256, NULL, 2, NULL);
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
