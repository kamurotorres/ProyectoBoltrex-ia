import React from 'react';
import { AlertTriangle, User } from 'lucide-react';
import { money as money0 } from '@/lib/format';
import PartySearchCard from '@/components/commerce/PartySearchCard';

// Paso 1 del POS. Diseño compartido con Compras (components/commerce/PartySearchCard, rama compras-estilo-pos).
export default function ClientSection({ creditStatus, filteredClients, handleClientChange, searchClient, searchingClients, selectedClient, setSearchClient, setSelectedClient }) {
  return (
    <PartySearchCard
      step={1}
      title="Seleccionar Cliente"
      icon={User}
      selected={!!selectedClient}
      selectedTitle={selectedClient && `${selectedClient.first_name} ${selectedClient.last_name}`}
      selectedLines={selectedClient && (
        <>
          <p className="text-sm text-muted-foreground font-mono">{selectedClient.document_number}</p>
          {selectedClient.price_list && (
            <p className="text-xs text-green-400">Lista de precios: {selectedClient.price_list}</p>
          )}
          {creditStatus && creditStatus.balance > 0 && (
            <p className="text-xs text-muted-foreground" data-testid="pos-client-balance">
              Debe {money0(creditStatus.balance)} en Fios
              {creditStatus.credit_limit ? ` · cupo disponible ${money0(creditStatus.available)} de ${money0(creditStatus.credit_limit)}` : ''}
            </p>
          )}
          {creditStatus && !creditStatus.balance && creditStatus.credit_limit && (
            <p className="text-xs text-muted-foreground">Cupo de crédito {money0(creditStatus.credit_limit)}</p>
          )}
        </>
      )}
      onClear={() => {
        setSelectedClient(null);
        setSearchClient('');
      }}
      changeLabel="Cambiar Cliente"
      hint="Busca y selecciona un cliente para continuar con la venta"
      placeholder="Buscar cliente por nombre o documento... (mínimo 2 caracteres)"
      query={searchClient}
      onQueryChange={setSearchClient}
      results={filteredClients}
      searching={searchingClients}
      resultKey={(client) => client.document_number}
      renderResult={(client) => ({
        title: `${client.first_name} ${client.last_name}`,
        subtitle: client.document_number,
        side: (
          <>
            {client.price_list && (
              <p className="text-sm text-primary">Lista: {client.price_list}</p>
            )}
            {client.phone && (
              <p className="text-xs text-muted-foreground">{client.phone}</p>
            )}
          </>
        ),
      })}
      onSelect={handleClientChange}
      noun="clientes"
      inputTestId="pos-search-client-input"
      rowTestId="pos-client"
    >
      {/* P2.30 (opción A): con facturas vencidas solo se avisa; la venta se permite. */}
      {selectedClient && creditStatus && creditStatus.overdue_balance > 0 && (
        <div className="mt-3 p-3 rounded-lg border border-red-500/40 bg-red-500/10 text-sm text-red-400 flex items-start gap-2" data-testid="pos-overdue-warning">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>
            Este cliente tiene <strong>{money0(creditStatus.overdue_balance)}</strong> vencidos en {creditStatus.overdue_invoices} factura(s)
            (la más atrasada: {creditStatus.max_days_overdue} día(s)). Puedes venderle, pero conviene cobrarle antes de fiarle más.
          </span>
        </div>
      )}
    </PartySearchCard>
  );
}
