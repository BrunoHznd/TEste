// tailwind.config.js
module.exports = {
  content: [
    "./AppHome/templates/**/*.html",
    "./AppHome/static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Tons derivados da logo:
        "mototec-teal": "#0D2B3E",    // cor escura do motociclista e do texto
        "mototec-bege": "#F5E9D0",   // fundo claro com grade
        "mototec-laranja": "#FFA726",// cor externa das bolhas
        "mototec-amarelo": "#FFEE58",// cor interna das bolhas
        "mototec-azul": "#1976D2",   // tom de azul para botões/hover
      },
      fontFamily: {
        // Caso queira usar uma fonte parecida com a tipografia da logo:
        sans: ["Poppins", "ui-sans-serif", "system-ui"],
        script: ["Pacifico", "cursive"],
      },
    },
  },
  plugins: [
    require("flowbite/plugin"),
  ],
};
