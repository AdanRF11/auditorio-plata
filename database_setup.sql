---

### Entregable 2: Script SQL Completo (Base de Datos)
Guarda este código en un archivo llamado `database_setup.sql`. Contiene toda la lógica de datos y el motor de exclusión mutua.

```sql
-- 1. Tabla de Control de Aforo
CREATE TABLE Evento (
    id_evento NUMBER PRIMARY KEY,
    nombre VARCHAR2(100) NOT NULL,
    aforo_total NUMBER NOT NULL,
    boletos_emitidos NUMBER DEFAULT 0 NOT NULL
);

-- 2. Inserción del evento (Límite: 20,000)
INSERT INTO Evento (id_evento, nombre, aforo_total, boletos_emitidos) 
VALUES (1, 'Auditorio Plata - Concierto Navideño', 20000, 0);

-- 3. Secuencia atómica para el folio
CREATE SEQUENCE seq_folio START WITH 1 INCREMENT BY 1 NOCACHE;

-- 4. Tabla de registro de boletos
CREATE TABLE Boleto (
    folio NUMBER PRIMARY KEY,
    id_evento NUMBER REFERENCES Evento(id_evento),
    fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
COMMIT;

-- 5. Procedimiento Almacenado con Mutex (SELECT ... FOR UPDATE)
CREATE OR REPLACE PROCEDURE emitir_boleto (
    p_id_evento IN NUMBER,
    p_folio OUT NUMBER,
    p_mensaje OUT VARCHAR2,
    p_fecha OUT VARCHAR2
) AS
    v_aforo_total NUMBER;
    v_emitidos NUMBER;
BEGIN
    -- Bloqueo exclusivo de fila (Prevención de Condición de Carrera)
    SELECT aforo_total, boletos_emitidos 
    INTO v_aforo_total, v_emitidos
    FROM Evento
    WHERE id_evento = p_id_evento
    FOR UPDATE; 

    IF v_emitidos < v_aforo_total THEN
        p_folio := seq_folio.NEXTVAL;
        INSERT INTO Boleto (folio, id_evento) VALUES (p_folio, p_id_evento);
        UPDATE Evento SET boletos_emitidos = boletos_emitidos + 1 WHERE id_evento = p_id_evento;
        
        p_fecha := TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS');
        p_mensaje := 'EXITO';
        COMMIT; 
    ELSE
        p_folio := 0;
        p_fecha := '';
        p_mensaje := 'RECHAZO: AFORO LLENO';
        ROLLBACK; 
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        p_folio := 0;
        p_fecha := '';
        p_mensaje := 'ERROR_INTERNO: ' || SQLERRM;
END;
/
