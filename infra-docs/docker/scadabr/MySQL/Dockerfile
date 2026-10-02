# syntax=docker/dockerfile:1
#
# ScadaBR 1.2 (https://github.com/ScadaBR/ScadaBR) on Tomcat 9 / Java 8
#
# Build:  docker build -t scadabr .
# Run:    docker run -p 8080:8080 -v scadabr-data:/data scadabr
# Open:   http://localhost:8080/ScadaBR   (login admin / admin)

############################
# Stage 1 – compile sources
############################
FROM eclipse-temurin:8-jdk AS build

ARG SCADABR_REPO=https://github.com/ScadaBR/ScadaBR.git
ARG SCADABR_REF=master

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch "${SCADABR_REF}" "${SCADABR_REPO}" .

# The project's build.xml needs svnant and runs the unit tests, so compile
# directly with javac. Every dependency already ships in WEB-INF/lib; the
# servlet/JSP APIs come from WEB-INF/tmp-lib (provided by Tomcat at runtime).
# Note: the br.org.scadabr.vo.permission classes are used by production code
# but live under test/ in the upstream repo, so they are compiled in too.
RUN set -eux; \
    { find src -name '*.java'; find test/br/org/scadabr/vo/permission -name '*.java'; } > /tmp/sources.txt; \
    mkdir -p /out/classes; \
    javac -nowarn -encoding UTF-8 \
          -cp "WebContent/WEB-INF/lib/*:WebContent/WEB-INF/tmp-lib/*" \
          -d /out/classes @/tmp/sources.txt; \
    # copy any non-Java resources living next to the sources
    (cd src && find . -type f ! -name '*.java' -exec cp --parents {} /out/classes/ \;); \
    # assemble the exploded webapp
    cp -r WebContent /out/ScadaBR; \
    rm -rf /out/ScadaBR/WEB-INF/tmp-lib; \
    # test-only jars are not needed at runtime
    rm -f /out/ScadaBR/WEB-INF/lib/junit-*.jar /out/ScadaBR/WEB-INF/lib/mockito-*.jar; \
    cp -r /out/classes/. /out/ScadaBR/WEB-INF/classes/

############################
# Stage 2 – runtime
############################
FROM tomcat:9.0-jdk8-temurin

LABEL org.opencontainers.image.title="ScadaBR" \
      org.opencontainers.image.source="https://github.com/ScadaBR/ScadaBR" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

# Default configuration (overridable at runtime, see docker-compose.yml)
ENV DB_TYPE=derby \
    DB_URL=/data/scadabrDB \
    DB_USERNAME= \
    DB_PASSWORD= \
    DB_POOL_MAX_ACTIVE=10 \
    DB_POOL_MAX_IDLE=10 \
    API_AUTHENTICATION=disabled \
    API_USERNAME=admin \
    API_PASSWORD=admin \
    TZ=America/Sao_Paulo \
    CATALINA_OPTS="-Xms256m -Xmx1024m -Djava.awt.headless=true"

RUN rm -rf /usr/local/tomcat/webapps/* \
 && mkdir -p /data

COPY --from=build /out/ScadaBR /usr/local/tomcat/webapps/ScadaBR
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# /data                       -> Derby database
# .../ScadaBR/uploads         -> images uploaded for graphical views
# .../ScadaBR/WEB-INF/filedata-> image data points
VOLUME ["/data", "/usr/local/tomcat/webapps/ScadaBR/uploads", "/usr/local/tomcat/webapps/ScadaBR/WEB-INF/filedata"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
  CMD curl -fsS -o /dev/null http://localhost:8080/ScadaBR/login.htm || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["catalina.sh", "run"]
