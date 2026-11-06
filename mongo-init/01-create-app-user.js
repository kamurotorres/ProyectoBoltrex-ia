// Boltrex (P2.25): crea el usuario de la aplicación al inicializar MongoDB por primera vez
// (volumen de datos vacío). Lo ejecuta la imagen oficial de Mongo ya autenticada como root.
// El backend se conecta con este usuario: solo puede leer/escribir su base, no administrar.
const user = process.env.MONGO_APP_USER || 'boltrex_app';
const pwd = process.env.MONGO_APP_PASSWORD;
const dbName = process.env.MONGO_APP_DB || 'boltrex';

if (!pwd) {
  throw new Error('Falta MONGO_APP_PASSWORD: defínela en el archivo .env (ver .env.example).');
}

const admin = db.getSiblingDB('admin');
if (admin.getUser(user)) {
  print(`[boltrex] El usuario ${user} ya existe.`);
} else {
  admin.createUser({ user, pwd, roles: [{ role: 'readWrite', db: dbName }] });
  print(`[boltrex] Usuario ${user} creado con readWrite sobre '${dbName}'.`);
}
