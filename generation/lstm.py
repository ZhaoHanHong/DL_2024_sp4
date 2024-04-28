import copy
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class BaseModel(nn.Module):

    def __init__(self, args, dictionary):
        super().__init__()
        self.padding_idx = dictionary.pad()
        self.dictionary = dictionary


class LMModel(BaseModel):

    def __init__(self, args, dictionary):
        super().__init__(args, dictionary)
        # Hint: Use len(dictionary) in __init__
        ##############################################################################
        #                  TODO: You need to complete the code here                  #
        ##############################################################################
        self.dict = dictionary
        self.dict_len = len(dictionary) # 7120
        self.embedding_dim = args.embedding_dim # 512
        self.hidden_size=args.hidden_size # 512
        self.num_layers = args.num_layers # 6
        self.lstm = nn.LSTM(self.embedding_dim,self.hidden_size,self.num_layers,batch_first=True)
        self.embedding = nn.Linear(self.dict_len,self.hidden_size)
        self.linear = nn.Linear(self.hidden_size,self.dict_len)
        ##############################################################################
        #                              END OF YOUR CODE                              #
        ##############################################################################

    def logits(self, source:torch.Tensor, **unused):
        """
        Compute the logits for the given source.

        Args:
            source: The input data.
            **unused: Additional unused arguments.

        Returns:
            logits: The computed logits.
        """
        ##############################################################################
        #                  TODO: You need to complete the code here                  #
        ##############################################################################            
        batch,leng = source.shape
        # print(self.dict.bos())
        # print(self.dict.eos())
        # print(source)
        # print('batch size',batch)
        src_raw = F.one_hot(source,num_classes=self.dict_len).to(torch.float)
        src_embedded = self.embedding(src_raw)# leng, batch, embedded_dim
        # print(src_embedded.shape)
        output,_ = self.lstm(src_embedded) # output: batch, leng, embedded_dim 
        # print(output.shape)
        logits = self.linear(output)
        # print('embedded shape',src_embedded.shape)
        # print(logits.shape)
        # logits = logits.transpose(1,2)
        # print('logits.shape',logits.shape)
        # logits.shape: batch, leng, word_dim
        ##############################################################################
        #                              END OF YOUR CODE                              #
        ##############################################################################
        return logits

    def get_loss(self, source, target, reduce=True, **unused):
        # print('target.shape',target.shape)
        # print('source',source[0])
        # print('target',target[0])
        logits = self.logits(source)
        # print('shape 1',logits.shape)
        lprobs = F.log_softmax(logits, dim=-1).view(-1, logits.size(-1))
        # print('shape 2',lprobs.shape)
        # print('target shape',target.shape)
        return F.nll_loss(
            lprobs,
            target.view(-1),
            ignore_index=self.padding_idx,
            reduction="sum" if reduce else "none",
        )

    @torch.no_grad()
    def generate(self, prefix, max_len=100, beam_size=None):
        """
        Generate text using the trained language model with beam search.

        Args:
            prefix (str): The initial words, like "白".
            max_len (int, optional): The maximum length of the generated text.
                                     Defaults to 100.
            beam_size (int, optional): The beam size for beam search. Defaults to None.

        Returns:
            outputs (str): The generated text.(e.g. "白日依山尽，黄河入海流，欲穷千里目，更上一层楼。")
        """
        ##############################################################################
        #                  TODO: You need to complete the code here                  #
        ##############################################################################
        prefix_sp = [c for c in prefix]
        print(prefix_sp)
        x = torch.tensor([self.dict.bos()]+[self.dict.index(c) for c in prefix_sp]).cuda()
        outputs = "<s>"+prefix
        
        if beam_size == None:
            beam_size = 1
        src_raw = F.one_hot(x,num_classes=self.dict_len).to(torch.float)
        src_embedded = self.embedding(src_raw)# leng, embedded_dim
        def embedd(index):
            new_src_raw = F.one_hot(torch.tensor([index]).cuda(),num_classes=self.dict_len).to(torch.float)
            return self.embedding(new_src_raw)
        bests = [(0,outputs,src_embedded,False)]
        # data structure:   
        # prob, output(str), history(tensor), stopped or not, (h,c)

        for round in range(1,max_len):
            # print('round',round)
            new_bests = []
            # print(bests)
            for prob,outputs,history,done in bests:
                if done:
                    new_bests.append((prob,outputs,history,done))
                    continue
                value,_ = self.lstm(history)
                logits = self.linear(value[-1,:])
                logits = F.log_softmax(logits,dim=-1) # this is the log prob
                for _ in range(beam_size):
                    ind = torch.argmax(logits,dim=0).item()
                    new_outputs = outputs+self.dict[ind]
                    new_prob = (prob + logits[ind].item())*(round/(round+1))
                    new_history = torch.cat((history,embedd(ind)),dim=0)
                    logits[ind] = -1e10
                    new_bests.append((new_prob,new_outputs,new_history,True if ind == self.dict.eos() else False))
            bests = sorted(new_bests)[-beam_size:] 
            # print(bests)
        return bests[-1][1]
        ##############################################################################
        #                              END OF YOUR CODE                              #
        ##############################################################################
        # outputs = ""
        return outputs


class Seq2SeqModel(BaseModel):

    def __init__(self, args, dictionary):
        super().__init__(args, dictionary)
        # Hint: Use len(dictionary) in __init__
        ##############################################################################
        #                  TODO: You need to complete the code here                  #
        ##############################################################################
        self.dict = dictionary
        self.dict_len = len(dictionary) # 7120
        self.embedding_dim = args.embedding_dim # 512
        self.hidden_size=args.hidden_size # 512
        self.num_layers = args.num_layers # 6
        self.encoder = nn.LSTM(self.embedding_dim,self.hidden_size,self.num_layers,batch_first=True,bidirectional=True)
        self.decoder = nn.LSTM(self.embedding_dim,self.hidden_size,self.num_layers,batch_first=True)
        self.embedding = nn.Linear(self.dict_len,self.hidden_size)
        self.linear = nn.Linear(self.hidden_size*2,self.dict_len)
        # self.middle = nn.Linear(4 * self.num_layers * self.embedding_dim, 2* self.num_layers * self.embedding_dim)
        self.device = args.device
        ##############################################################################
        #                              END OF YOUR CODE                              #
        ##############################################################################

    def logits(self, source, prev_outputs, **unused):
        """
        Compute the logits for the given source and previous outputs.

        Args:
            source: The input data.
            prev_outputs: The previous outputs.
            **unused: Additional unused arguments.

        Returns:
            logits: The computed logits.
        """
        ##############################################################################
        #                  TODO: You need to complete the code here                  #
        ##############################################################################
        
        # source pass through encoder to get hidden state
        batch,leng = source.shape
        # print('batch size',batch)
        # print('length',leng)
        src_raw = F.one_hot(source,num_classes=self.dict_len).to(torch.float)
        src_embedded = self.embedding(src_raw)# batch, length, embedded_dim
        # print(src_embedded.shape)
        out,(h,c) = self.encoder(src_embedded) # h: num_layer * 2, batch, embedding_dim
        out = (out[...,:self.embedding_dim]+out[...,self.embedding_dim:2*(self.embedding_dim)])/2
        # print('out.shape',out.shape)
        # print('encoder,h.shape',h.shape)
        # hc = torch.cat((h.transpose(0,1).reshape(batch,-1),c.transpose(0,1).reshape(batch,-1)),dim=1)
        # print('hc.shape',hc.shape)

        # hc_in = self.middle(hc).reshape(batch,self.num_layers * 2,-1)
        # print('c.shape',c.shape)
        h_in, c_in = c[:self.num_layers,:,:], c[self.num_layers:,:,:]
        # print('h_in.shape',h_in.shape)
        # print('c_in.shape',c_in.shape)
        h_in = h_in.contiguous()
        c_in = c_in.contiguous()
        # print(h_in.shape)
        # hidden state pass through decoder to get outputs
        prev_raw = F.one_hot(prev_outputs,num_classes=self.dict_len).to(torch.float)
        prev_embedded = self.embedding(prev_raw)# batch, length, embedded_dim
        final_out,_ = self.decoder(prev_embedded,(h_in,c_in)) # h: num_layer, batch, embedding_dim
        # attention
        # h_att = torch.zeros([batch,leng,self.hidden_size]).to(self.device)
        # for i in range(prev_embedded.shape[1]):
        #     # print(final_out[:,i:i+1,...].shape)
        #     # print(out.shape)
        #     att_scores = final_out[:,i:i+1,...] * out
        #     # print('att_scores',att_scores)
        #     att_scores = F.softmax(att_scores,dim=1)
        #     # print((att_scores * out[i]).shape)
        #     h_att[:,i,:] = (att_scores * out).sum(dim=1)
            # print(h_att.shape)
            # assert False
        new_h_att_sc = final_out.unsqueeze(2) * out.unsqueeze(1)
        new_h_att_sc = F.softmax(new_h_att_sc,dim=2)
        new_h_att = (new_h_att_sc * out.unsqueeze(1)).sum(dim=2)
        # print(h_att)
        # print(h_att.shape)
        # print(final_out.shape)
        information = torch.cat((new_h_att,final_out),dim=2)
        
        # print('decoder:h.shape',h.shape)
        logits = self.linear(information)
        # raise NotImplementedError()
        # logits = logits.transpose(1,2)
        # print(logits.shape)
        # assert(False)
        ##############################################################################
        #                              END OF YOUR CODE                              #
        ##############################################################################
        return logits

    def get_loss(self, source, prev_outputs, target, reduce=True, **unused):
        logits = self.logits(source, prev_outputs)
        lprobs = F.log_softmax(logits, dim=-1).view(-1, logits.size(-1))
        # print(source[0])
        # print(prev_outputs[0])
        # print(target[0])
        return F.nll_loss(
            lprobs,
            target.view(-1),
            ignore_index=self.padding_idx,
            reduction="sum" if reduce else "none",
        )

    @torch.no_grad()
    def generate(self, inputs, max_len=100, beam_size=None):
        """
        Generate text using the trained sequence-to-sequence model with beam search.

        Args:
            inputs (str): The input text, e.g., "改革春风吹满地".
            max_len (int, optional): The maximum length of the generated text.
                                     Defaults to 100.
            beam_size (int, optional): The beam size for beam search. Defaults to None.

        Returns:
            outputs (str): The generated text, e.g., "复兴政策暖万家".
        """
        # Hint: Use dictionary.encode_line and dictionary.bos() or dictionary.eos()
        ##############################################################################
        #                  TODO: You need to complete the code here                  #
        ##############################################################################
        inputs = self.dict.encode_line(inputs).to(torch.long)
        if len(inputs)<20:
            inputs = torch.cat((torch.tensor([self.dict.bos()],dtype=torch.long),inputs[:-1]
                            ,torch.ones([20-len(inputs)],dtype=torch.long)
                            ),dim=0)
        else:
            inputs = torch.cat((torch.tensor([self.dict.bos()],dtype=torch.long),inputs[:-1]),dim=0)
        print('inpts',inputs)
        if beam_size == None:
            beam_size = 1
        leng = inputs.shape[0]
        # print('batch size',batch)
        src_raw = F.one_hot(inputs,num_classes=self.dict_len).to(torch.float).cuda()
        src_embedded = self.embedding(src_raw) # batch, length, embedded_dim
        # print('source shape',src_embedded.shape)
        # print('h.shape',h.shape)
        encoder_out,(h,c) = self.encoder(src_embedded) # h: num_layer * 2, batch, embedding_dim
        # print('encoder_out.shape',encoder_out.shape)
        encoder_out = (encoder_out[...,:self.embedding_dim]+encoder_out[...,self.embedding_dim:2*(self.embedding_dim)])/2
        # print('c.shape',c.shape)
        h_in, c_in = c[:self.num_layers,:], c[self.num_layers:,:]
        # print('h_in.shape',h_in.shape)
        h_in = h_in.contiguous()
        c_in = c_in.contiguous()
        # print(h_in.shape)
        # hidden state pass through decoder to get outputs
        outputs = self.dict[self.dict.bos()]
        
        def embedd(index):
            new_src_raw = F.one_hot(torch.tensor([index]).to('cuda'),num_classes=self.dict_len).to(torch.float)
            return self.embedding(new_src_raw)

        prev_embedded = embedd(self.dict.bos())# batch, length, embedded_dim
        # print('decoder - h.shape',h.shape) 
        bests = [(0,outputs,prev_embedded,False)]
        
        for round in range(1,max_len):
            # print('round',round)
            new_bests = []
            # print(bests)
            for prob,outputs,history,done in bests:
                if done:
                    new_bests.append((prob,outputs,history,done))
                    continue
                # print('history.shape',history.shape)
                final_out,(tupl) = self.decoder(history,(h_in,c_in))
                new_h_att_sc = final_out[-1:,:] * encoder_out
                new_h_att_sc = F.softmax(new_h_att_sc,dim=0)
                new_h_att = (new_h_att_sc * encoder_out).sum(dim=0)
                # print('1',new_h_att)
                # print('2',final_out[-1])
                # print(new_h_att.shape)
                # print(final_out.shape)
                logits = self.linear(torch.cat((new_h_att,final_out[-1]),dim=0))
                logits = F.log_softmax(logits,dim=-1) # log prob
                for _ in range(beam_size):
                    ind = torch.argmax(logits,dim=0).item()
                    new_outputs = outputs+self.dict[ind]
                    new_prob = (prob + logits[ind].item())*(round/(round+1))
                    new_history = torch.cat((history,embedd(ind)),dim=0)
                    logits[ind] = -1e10
                    new_bests.append((new_prob,new_outputs,new_history,True if ind == self.dict.eos() else False))
            bests = sorted(new_bests)[-beam_size:] 
            # print(bests)
        return bests[-1][1]
        # raise NotImplementedError()
        ##############################################################################
        #                              END OF YOUR CODE                              #
        ##############################################################################
        outputs = ""
        return outputs
