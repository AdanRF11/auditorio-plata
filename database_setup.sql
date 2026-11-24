-- =========================================================================
-- AUDITORIO PLATA - ESQUEMA RELACIONAL Y CONTROL DE CONCURRENCIA (ORACLE)
-- Ejecutar en: sqlplus system/Admin1234@FREEPDB1
-- =========================================================================

-- 1. Tabla Principal del Evento (Control Global de Aforo)
CREATE TABLE Evento (
    id_evento NUMBER PRIMARY KEY,
    nombre VARCHAR2(100) NOT NULL,
    aforo_total NUMBER NOT NULL,
    boletos_emitidos NUMBER DEFAULT 0 NOT NULL,
    CONSTRAINT chk_evento_aforo CHECK (boletos_emitidos <= aforo_total)
);

-- Inserción del evento principal (Aforo total: 20,000 localidades)
INSERT INTO Evento (id_evento, nombre, aforo_total, boletos_emitidos) 
VALUES (1, 'Auditorio Plata - Concierto Navideño 2026', 20000, 0);

-- 2. Tabla de Zonas (Control Granular por Área)
CREATE TABLE Zona (
    id_zona VARCHAR2(20) PRIMARY KEY,
    nombre VARCHAR2(50) NOT NULL,
    aforo_total NUMBER NOT NULL,
    boletos_emitidos NUMBER DEFAULT 0 NOT NULL,
    CONSTRAINT chk_zona_aforo CHECK (boletos_emitidos <= aforo_total)
);

-- Distribución oficial de las 20,000 localidades en 3 áreas
INSERT INTO Zona (id_zona, nombre, aforo_total, boletos_emitidos) VALUES ('VIP', 'Zona VIP', 500, 0);
INSERT INTO Zona (id_zona, nombre, aforo_total, boletos_emitidos) VALUES ('PLATA', 'Zona Plata', 1500, 0);
INSERT INTO Zona (id_zona, nombre, aforo_total, boletos_emitidos) VALUES ('GENERAL', 'Zona General', 18000, 0);

-- 3. Secuencia atómica para generación de folios únicos sin saltos en caché
CREATE SEQUENCE seq_folio START WITH 1 INCREMENT BY 1 NOCACHE;

-- 4. Tabla de Registro Histórico de Boletos Emitidos
CREATE TABLE Boleto (
    folio NUMBER PRIMARY KEY,
    id_evento NUMBER NOT NULL REFERENCES Evento(id_evento),
    id_zona VARCHAR2(20) NOT NULL REFERENCES Zona(id_zona),
    asiento VARCHAR2(20) UNIQUE NOT NULL,
    fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

COMMIT;

-- 5. Procedimiento Almacenado con Exclusión Mutua Granular (SELECT ... FOR UPDATE)
CREATE OR REPLACE PROCEDURE emitir_boleto (
    p_id_evento IN NUMBER,
    p_id_zona IN VARCHAR2,
    p_folio OUT NUMBER,
    p_asiento OUT VARCHAR2,
    p_mensaje OUT VARCHAR2,
    p_fecha OUT VARCHAR2
) AS
    v_aforo_zona NUMBER;
    v_emitidos_zona NUMBER;
    v_num_asiento NUMBER;
BEGIN
    -- Bloqueo exclusivo a nivel de fila (Mutex) sobre la zona solicitada.
    -- Evita condiciones de carrera y permite ventas paralelas entre distintas zonas.
    SELECT aforo_total, boletos_emitidos 
    INTO v_aforo_zona, v_emitidos_zona
    FROM Zona
    WHERE id_zona = UPPER(p_id_zona)
    FOR UPDATE;

    IF v_emitidos_zona < v_aforo_zona THEN
        p_folio := seq_folio.NEXTVAL;
        v_num_asiento := v_emitidos_zona + 1;
        
        -- Asignación de etiqueta de asiento única y consecutiva por área
        IF UPPER(p_id_zona) = 'VIP' THEN
            p_asiento := 'VIP-' || LPAD(v_num_asiento, 3, '0');
        ELSIF UPPER(p_id_zona) = 'PLATA' THEN
            p_asiento := 'PLATA-' || LPAD(v_num_asiento, 4, '0');
        ELSE
            p_asiento := 'GENERAL-' || LPAD(v_num_asiento, 5, '0');
        END IF;

        -- Persistencia del boleto y actualización de contadores
        INSERT INTO Boleto (folio, id_evento, id_zona, asiento) 
        VALUES (p_folio, p_id_evento, UPPER(p_id_zona), p_asiento);
        
        UPDATE Zona SET boletos_emitidos = v_num_asiento WHERE id_zona = UPPER(p_id_zona);
        UPDATE Evento SET boletos_emitidos = boletos_emitidos + 1 WHERE id_evento = p_id_evento;
        
        p_fecha := TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS');
        p_mensaje := 'EXITO';
        COMMIT; -- Libera el bloqueo exclusivo y confirma la transacción (ACID)
    ELSE
        -- Rechazo determinista cuando la zona alcanza su capacidad máxima
        p_folio := 0;
        p_asiento := '';
        p_fecha := '';
        p_mensaje := 'RECHAZO: ' || UPPER(p_id_zona) || ' AGOTADA';
        ROLLBACK; -- Libera el bloqueo sin alterar datos
    END IF;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        ROLLBACK;
        p_folio := 0;
        p_asiento := '';
        p_fecha := '';
        p_mensaje := 'ERROR: ZONA NO VALIDA';
    WHEN OTHERS THEN
        ROLLBACK;
        p_folio := 0;
        p_asiento := '';
        p_fecha := '';
        p_mensaje := 'ERROR_INTERNO: ' || SQLERRM;
END;
/

-- =========================================================================
-- BLOQUES AUXILIARES DE MANTENIMIENTO Y PRUEBAS (DESCOMENTAR SEGÚN SE REQUIERA)
-- =========================================================================

-- -------------------------------------------------------------------------
-- CASO A: REINICIO TOTAL DE CONTEO, ZONAS, ASIENTOS Y FOLIOS
-- Útil después de ejecutar pruebas de estrés (spawner.py) para devolver el
-- auditorio a 0 boletos emitidos y restaurar los 20,000 lugares originales.
-- -------------------------------------------------------------------------
-- DELETE FROM Boleto;
-- UPDATE Evento SET aforo_total = 20000, boletos_emitidos = 0 WHERE id_evento = 1;
-- UPDATE Zona SET aforo_total = 500, boletos_emitidos = 0 WHERE id_zona = 'VIP';
-- UPDATE Zona SET aforo_total = 1500, boletos_emitidos = 0 WHERE id_zona = 'PLATA';
-- UPDATE Zona SET aforo_total = 18000, boletos_emitidos = 0 WHERE id_zona = 'GENERAL';
-- DROP SEQUENCE seq_folio;
-- CREATE SEQUENCE seq_folio START WITH 1 INCREMENT BY 1 NOCACHE;
-- COMMIT;

-- -------------------------------------------------------------------------
-- CASO B: CONFIGURACIÓN DE AFORO REDUCIDO PARA PRUEBA DE SOLD OUT (BARRERA)
-- Reduce temporalmente el cupo de la zona GENERAL a 50 lugares para validar
-- que ataque_barrera.py (100 hilos simultáneos) emita exactamente 50 boletos
-- y rechace 50 sin sobreventa. (Ejecutar CASO A al terminar para restaurar).
-- -------------------------------------------------------------------------
-- DELETE FROM Boleto;
-- UPDATE Zona SET boletos_emitidos = 0 WHERE id_zona IN ('VIP', 'PLATA');
-- UPDATE Zona SET aforo_total = 50, boletos_emitidos = 0 WHERE id_zona = 'GENERAL';
-- UPDATE Evento SET aforo_total = 2050, boletos_emitidos = 0 WHERE id_evento = 1;
-- DROP SEQUENCE seq_folio;
-- CREATE SEQUENCE seq_folio START WITH 1 INCREMENT BY 1 NOCACHE;
-- COMMIT;

-- -------------------------------------------------------------------------
-- CASO C: ELIMINACIÓN COMPLETA DEL ESQUEMA (REINSTALACIÓN DESDE CERO)
-- Borra todas las tablas, secuencias y procedimientos del proyecto.
-- -------------------------------------------------------------------------
-- DROP PROCEDURE emitir_boleto;
-- DROP TABLE Boleto;
-- DROP TABLE Zona;
-- DROP TABLE Evento;
-- DROP SEQUENCE seq_folio;
-- COMMIT;
