$ca = 'C:\Users\ricar\source\repos\ESP32\baltimore2.crt'


$ca = 'C:\Users\ricar\source\repos\ESP32\DigiCertGlobalRootG2.crt.pem'





mosquitto_pub -h master-esp32.azure-devices.net -p 8883 --cafile C:\Users\ricar\source\repos\ESP32\BaltimoreCyberTrustRoot.crt.pem `
  -t devices/esp32/messages/events/ -m '{"test":1}' `
  -u "master-esp32.azure-devices.net/esp32/?api-version=2018-06-30" `
  -P "SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=0oP%2FgFZTfCdp%2Fuc1e9iAoxI3gtjzqdb2StBtqfhsYCE%3D&se=1760628125"



mosquitto_pub -d `
  -h master-esp32.azure-devices.net -p 8883 `
  --cafile $ca `
  -t "devices/esp32/messages/events/" `
  -m '{"test":1}' `
  -u "master-esp32.azure-devices.net/esp32/?api-version=2018-06-30" `
  -i "esp32" `
  -P 'SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=0oP%2FgFZTfCdp%2Fuc1e9iAoxI3gtjzqdb2StBtqfhsYCE%3D&se=1760628125'



cd C:\Users\ricar\source\repos\ESP32




mosquitto_pub -d -h master-esp32.azure-devices.net -p 8883 --insecure `
  -t "devices/esp32/messages/events/" -m '{"test":1}' `
  -u "master-esp32.azure-devices.net/esp32/?api-version=2018-06-30" `
  -i "esp32" `
  -P 'SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=0oP%2FgFZTfCdp%2Fuc1e9iAoxI3gtjzqdb2StBtqfhsYCE%3D&se=1760628125'



openssl s_client -connect master-esp32.azure-devices.net:8883 -showcerts


openssl s_client -connect master-esp32.azure-devices.net:8883 -servername master-esp32.azure-devices.net -showcerts


openssl s_client -connect master-esp32.azure-devices.net:8883 -servername master-esp32.azure-devices.net -showcerts -CAfile $ca


Test-NetConnection -ComputerName master-esp32.azure-devices.net -Port 8883



openssl version
mosquitto_pub -h


SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=bT2qdgkmuwTvOgS1cs2A9yH0Dsy5IoRwNwcXZqH%2Fv9w%3D&se=1760659242

SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=3o%2BSWNDkmYA0hChdDlTcqAC142oPjFiX1%2FBKiQmd%2BMU%3D&se=1760659181

# esp32-dev

mosquitto_pub -d `
  -h master-esp32.azure-devices.net -p 8883 `
  --cafile $ca `
  -t "devices/esp32/messages/events/" `
  -m '{"test":1}' `
  -u "master-esp32.azure-devices.net/esp32-dev/?api-version=2018-06-30" `
  -i "esp32-dev" `
  -P 'SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32-dev&sig=nz2wvdcyHqI9fFElksDBt5oWFGSfEUOxRHAjuv4CEMU%3D&se=1760660883'


# esp32
SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=WhXRbmVdrVEjJDgI0BIjPrK%2BLwx0JXWj1I%2BHBGr%2BU6g%3D&se=1760663896

$sas = 'SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=%2FMCmutkVSRAmHFE1f1FzUKJ4S5txaYgNOpJB0F%2B5%2F8M%3D&se=1760665955'

$sas = 'SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=BKpHclaaZjckmJ8wbriIF0FCYLTkcxfTEOEHGfdz6DI%3D&se=1760661094'



$sas = 'SharedAccessSignature sr=master-esp32.azure-devices.net%2Fdevices%2Fesp32&sig=jusQx5lByLeOMCClcCVQ0wO7D227M4P2P%2FFGRt03VXg%3D&se=1760665557'



mosquitto_pub -d `
  -h master-esp32.azure-devices.net -p 8883 `
  --cafile $ca `
  -t "devices/esp32/messages/events/" `
  -m '{"test":1}' `
  -u "master-esp32.azure-devices.net/esp32/?api-version=2018-06-30" `
  -i "esp32" `
  -P $sas



