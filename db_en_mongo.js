// Asegúrate de estar en la base de datos correcta
use vehiculos

// Insertar la lista completa de vehículos
db.vehiculos.insertMany([
  {
    "Vehiculo": "Motocicleta",
    "Categoria": "terrestre",
    "Peso/Ton": 0.5,
    "Descripcion": "Ruedass"
  },
  {
    "Vehiculo": "Auto",
    "Categoria": "terrestre",
    "Peso/Ton": 1.5,
    "Descripcion": "4 llantas"
  },
  {
    "Vehiculo": "Camión",
    "Categoria": "terrestre",
    "Peso/Ton": 12,
    "Descripcion": "Grandote"
  },
  {
    "Vehiculo": "Bicicleta",
    "Categoria": "terrestre",
    "Peso/Ton": 0.015,
    "Descripcion": "Bicicleta de montaña color negro"
  },
  {
    "Vehiculo": "Avión",
    "Categoria": "aéreo",
    "Peso/Ton": 45,
    "Descripcion": "Avión comercial de pasajeros de mediano alcance"
  },
  {
    "Vehiculo": "Helicóptero",
    "Categoria": "aéreo",
    "Peso/Ton": 2.5,
    "Descripcion": "Helicóptero de rescate ligero"
  },
  {
    "Vehiculo": "Barco",
    "Categoria": "Maritimo",
    "Peso/Ton": 500,
    "Descripcion": "Buque de carga transatlántico"
  }
])