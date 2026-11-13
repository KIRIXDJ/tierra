{
  description = "Entorno de desarrollo Python reproducible con Nix";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      # ═══════════════════════════════════════════════════════════════════
      #  ⚙️  CONFIGURACION — lo unico que sueles tocar
      # ═══════════════════════════════════════════════════════════════════

      # Version del INTERPRETE. En nixpkgs 26.05 hay "3.11" a "3.15".
      # OJO: esto NO fija tus dependencias; esas viven en .venv y las resuelve
      # uv/pip. Nix pone el interprete y las herramientas, no el ecosistema.
      pythonVersion = "3.14";

      # Crear y activar .venv al entrar al shell:
      #   true  -> `nix develop` te deja el prompt con el venv activado.
      #   false -> si tu flujo es `uv sync`, Poetry o PDM y gestionas tu el venv.
      autoVenv = true;

      # ═══════════════════════════════════════════════════════════════════

      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      # Aqui basta legacyPackages: no inyectamos overlays. (Compara con el
      # template Rust, que necesita `import nixpkgs` para rust-overlay.)
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs:
        let
          inherit (pkgs) lib;

          # "3.14" -> "python314"
          python = pkgs."python${lib.replaceStrings [ "." ] [ "" ] pythonVersion}";

          # Lo que diga el store manda. Si algun dia el atributo `python314`
          # apuntase a otra version, el aviso del shell y los `checks` lo delatan.
          pyVersion = lib.versions.majorMinor python.version;

          # Paquetes del SISTEMA, no de pip. Aqui van:
          #   - libs que las wheels cargan con dlopen (libpq, cairo, libGL...)
          #   - toolchains que necesitan los sdist al compilar (cmake, pkg-config)
          # Ejemplo:
          #   extraPackages = with pkgs; [ libpq openssl cmake pkg-config ];
          extraPackages = with pkgs; [ ];
        in
        {
          default = pkgs.mkShell {
            name = "python${pyVersion}-dev";

            packages = [ python pkgs.uv pkgs.ruff ] ++ extraPackages;

            # Para que las wheels que hacen dlopen encuentren lo de
            # extraPackages sin recompilarse en el proyecto.
            LD_LIBRARY_PATH = lib.makeLibraryPath extraPackages;

            # `~/.local/lib/python3.X/site-packages` se cuela en el shell aunque
            # Nix haya puesto su python delante: un `pip install --user` de otra
            # epoca rompe la reproducibilidad. Esto lo corta de raiz.
            PYTHONNOUSERSITE = "1";

            # uv se descarga sus propios CPython (python-build-standalone) si el
            # del sistema no le vale. Aqui el interprete es el de Nix y punto:
            # sin descargas y sin sorpresas de version.
            UV_PYTHON_DOWNLOADS = "never";

            # uv instala por hardlink desde su cache (~/.cache/uv). Si el
            # proyecto esta en otro sistema de archivos que la cache (WSL sobre
            # /mnt/c, unidades de red, tmpfs) el hardlink falla y uv avisa en
            # cada instalacion: `copy` cambia ese ruido por algo mas de disco.
            UV_LINK_MODE = "copy";

            shellHook = ''
              echo ""
              echo "  🐍 Python ${python.version}  ·  shell: python${pyVersion}-dev"
              echo "  ├─ interprete: ${python}/bin/python3"
              echo "  └─ ruff $(ruff --version 2>/dev/null | cut -d' ' -f2)  ·  uv $(uv --version 2>/dev/null | cut -d' ' -f2)"

              # ── Fugas: pyenv, conda, asdf, /usr/bin ──
              # En vez de buscar rutas conocidas, miramos de donde sale el
              # `python3` que se usaria de verdad. Si ya hay un venv activo no
              # se comprueba: ahi `python3` es el del venv, que es un enlace al
              # de Nix (y si no lo fuera, el aviso de abajo lo dice).
              if [ -z "''${VIRTUAL_ENV:-}" ]; then
                py_actual="$(command -v python3 2>/dev/null || true)"
                case "$py_actual" in
                  "" | /nix/store/*) : ;;
                  *)
                    echo ""
                    echo "  ⚠  python3 NO viene de Nix sino de $py_actual"
                    echo "     (pyenv, conda, asdf o el python del sistema se cuelan por delante)."
                    ;;
                esac
              fi

              ${lib.optionalString autoVenv ''
                # ── venv del proyecto ──
                # Nix da el interprete; las dependencias viven en .venv. Aqui no
                # se instala nada: solo se crea (si falta) y se activa.
                #
                # El venv va en la RAIZ del proyecto y no donde estes parado:
                # entrar desde src/ no debe crear un segundo .venv vacio al
                # lado del codigo. `nix develop` sube buscando el flake.nix;
                # hacemos lo mismo para encontrar la raiz.
                raiz="$PWD"
                while [ "$raiz" != "/" ] && [ ! -f "$raiz/flake.nix" ]; do
                  raiz="$(dirname "$raiz")"
                done
                [ -f "$raiz/flake.nix" ] || raiz="$PWD"
                venv="$raiz/.venv"

                if [ -f "$venv/bin/activate" ]; then
                  if [ "''${VIRTUAL_ENV:-}" != "$venv" ]; then
                    . "$venv/bin/activate"
                  fi

                  # Un .venv viejo apunta al python del store que lo creo y
                  # shadowea al del flake en silencio. Mejor avisar.
                  # Se interroga el binario del venv por ruta absoluta a
                  # proposito: si es un enlace roto, bash lo salta al buscar en
                  # el PATH y acabaria usando el python de Nix sin decir nada.
                  py_venv="$("$venv/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
                  if [ -z "$py_venv" ]; then
                    echo ""
                    echo "  ⚠  $venv no arranca: el python del store que lo creo ya no existe"
                    echo "     (¿pasaste nix-collect-garbage?). Recrealo:"
                    echo "       rm -rf \"$venv\"  &&  exit  y vuelve a entrar"
                  elif [ "$py_venv" != "${pyVersion}" ]; then
                    echo ""
                    echo "  ⚠  $venv se creo con Python $py_venv y el flake trae ${pyVersion}."
                    echo "     Los binarios nativos de ese venv no valen aqui. Recrealo:"
                    echo "       rm -rf \"$venv\"  &&  exit  y vuelve a entrar"
                  fi
                else
                  echo ""
                  echo "  · no hay .venv: creando uno con Python ${python.version} ..."
                  # `python -m venv` funciona sin red y trae pip dentro del venv
                  # (ensurepip). `uv venv` a secas NO instala pip: hace falta
                  # --seed. Preferimos el de la stdlib para que entrar al shell
                  # nunca dependa de la red.
                  if ${python}/bin/python3 -m venv "$venv"; then
                    . "$venv/bin/activate"
                    echo "  ✔ .venv listo — siguiente paso: uv pip install -r requirements.txt"
                  else
                    echo "  ⚠  no pude crear $venv (¿proyecto de solo lectura?)"
                    echo "     el python de Nix sigue en el PATH; crealo a mano cuando puedas."
                  fi
                fi
              ''}

              echo ""
            '';
          };
        });

      formatter = forAllSystems (pkgs: pkgs.nixfmt);

      # `nix flake check` construye esto en cada sistema. No es decorativo:
      # cada check cubre una forma real de romperse que evaluar no detecta.
      checks = forAllSystems (pkgs:
        let
          inherit (pkgs) lib;
          python = pkgs."python${lib.replaceStrings [ "." ] [ "" ] pythonVersion}";
        in
        {
          # 1. El atributo `pythonNNN` es de verdad la version pedida.
          #    (En java paso algo parecido: nixpkgs retiro JDKs y el nombre
          #    del atributo seguia ahi, apuntando a otra cosa.)
          version = pkgs.runCommand "check-python-version" { } ''
            real="$(${python}/bin/python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
            if [ "$real" != "${pythonVersion}" ]; then
              echo "pythonVersion = ${pythonVersion}, pero ${python} es $real" >&2
              exit 1
            fi
            touch $out
          '';

          # 2. `python -m venv` funciona y deja pip dentro. Si nixpkgs rompe
          #    ensurepip, el shellHook que crea .venv fallaria al entrar.
          venv = pkgs.runCommand "check-python-venv" { } ''
            ${python}/bin/python3 -m venv $TMPDIR/venv
            $TMPDIR/venv/bin/python -m pip --version
            touch $out
          '';

          # 3. uv crea el venv con el interprete de Nix y SIN red: el sandbox
          #    de Nix no tiene red, asi que si uv intentase descargarse un
          #    CPython, este check falla. Eso es justo lo que promete
          #    UV_PYTHON_DOWNLOADS=never.
          uv-offline = pkgs.runCommand "check-uv-offline" { } ''
            export HOME=$TMPDIR
            export UV_CACHE_DIR=$TMPDIR/uv-cache
            export UV_PYTHON_DOWNLOADS=never
            ${pkgs.uv}/bin/uv venv --python ${python}/bin/python3 $TMPDIR/venv
            $TMPDIR/venv/bin/python -c 'import sys; print(sys.executable)'
            touch $out
          '';
        });
    };
}
