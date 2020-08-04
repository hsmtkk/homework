--
-- PostgreSQL database dump
--

-- Dumped from database version 12.3
-- Dumped by pg_dump version 12.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: aifxapp_usdjpy15m; Type: TABLE; Schema: public; Owner: ken
--

CREATE TABLE public.aifxapp_usdjpy15m (
    "time" time without time zone NOT NULL,
    open double precision NOT NULL,
    close double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    volume integer NOT NULL
);


ALTER TABLE public.aifxapp_usdjpy15m OWNER TO ken;

--
-- Name: aifxapp_usdjpy15m aifxapp_usdjpy_pkey; Type: CONSTRAINT; Schema: public; Owner: ken
--

ALTER TABLE ONLY public.aifxapp_usdjpy15m
    ADD CONSTRAINT aifxapp_usdjpy_pkey PRIMARY KEY ("time");


--
-- PostgreSQL database dump complete
--

