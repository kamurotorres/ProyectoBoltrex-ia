import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, AlertTriangle, Search, User } from 'lucide-react';
import { money as money0 } from '@/lib/format';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

// Extraído de POS.js (mantenimiento fase 5) sin cambios en el JSX.
export default function ClientSection({ creditStatus, filteredClients, handleClientChange, searchClient, searchingClients, selectedClient, setSearchClient, setSelectedClient }) {
  return (
    <Card className={`w-full ${!selectedClient ? 'border-orange-500/50 bg-orange-500/5' : 'border-green-500/50 bg-green-500/5'}`}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <User className="h-5 w-5" />
          1. Seleccionar Cliente
          <span className="text-xs text-orange-500 font-normal">(Requerido)</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {selectedClient ? (
          <div className="flex items-center justify-between p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                <User className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="font-semibold text-lg">{`${selectedClient.first_name} ${selectedClient.last_name}`}</p>
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
              </div>
            </div>
            <Button
              variant="outline"
              onClick={() => {
                setSelectedClient(null);
                setSearchClient('');
              }}
            >
              Cambiar Cliente
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2 p-3 bg-orange-500/10 border border-orange-500/30 rounded-md">
              <AlertCircle className="h-5 w-5 text-orange-400" />
              <p className="text-sm text-orange-400">Busca y selecciona un cliente para continuar con la venta</p>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Buscar cliente por nombre o documento... (mínimo 2 caracteres)"
                value={searchClient}
                onChange={(e) => setSearchClient(e.target.value)}
                className="pl-10 text-lg h-12"
                data-testid="pos-search-client-input"
              />
            </div>

            {/* Show clients only when searching */}
            {searchClient.length >= 2 && (
              <div className="border rounded-lg overflow-hidden">
                {filteredClients.length > 0 ? (
                  <div className="divide-y">
                    {filteredClients.map((client, index) => (
                      <div
                        key={client.document_number}
                        className="flex items-center justify-between p-4 cursor-pointer hover:bg-accent transition-all"
                        onClick={() => handleClientChange(client)}
                        data-testid={`pos-client-${index}`}
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                            <User className="h-5 w-5 text-primary" />
                          </div>
                          <div>
                            <p className="font-medium">{`${client.first_name} ${client.last_name}`}</p>
                            <p className="text-sm text-muted-foreground font-mono">{client.document_number}</p>
                          </div>
                        </div>
                        <div className="text-right mr-4">
                          {client.price_list && (
                            <p className="text-sm text-primary">Lista: {client.price_list}</p>
                          )}
                          {client.phone && (
                            <p className="text-xs text-muted-foreground">{client.phone}</p>
                          )}
                        </div>
                        <Button size="sm">
                          Seleccionar
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center text-muted-foreground">
                    <User className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>{searchingClients ? 'Buscando…' : `No se encontraron clientes para "${searchClient}"`}</p>
                  </div>
                )}
              </div>
            )}

            {searchClient.length > 0 && searchClient.length < 2 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                Escribe al menos 2 caracteres para buscar clientes
              </p>
            )}
          </div>
        )}
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
      </CardContent>
    </Card>
  );
}
